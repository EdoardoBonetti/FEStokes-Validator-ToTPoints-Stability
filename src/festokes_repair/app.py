from webapp_client.app import App
from webapp_client.components import *
from webapp_client.qcomponents import *
from webapp_client.visualization import SolutionWebgui, PlotlyComponent
from webapp_client.utils import load_image
import netgen.occ as ngocc
import ngsolve as ngs
import os


def image(filename):
    picture = os.path.join(os.path.dirname(__file__), "assets", filename)
    return load_image(picture)


mesh_cards = {
    "Unstructured Mesh": {"image": "mesh/stdmesh.webp", "points": 2},
    "Curved Mesh": {"image": "mesh/curvedmesh.webp", "points": 4},
    "Type One Mesh": {"image": "mesh/typeonemesh.webp", "points": 1},
    "Singular Vertex Mesh": {"image": "mesh/crisscross.webp", "points": 3},
    "None": {"image": "mesh/emptymesh.webp", "points": 0},
}

pressure_cards = {
    "P0": {"image": "pressure/Pzeropressure.webp", "points": 1},
    "P1": {"image": "pressure/Ponepressure.webp", "points": 2},
    "P1*": {"image": "pressure/Ponedpressure.webp", "points": 2},
    "P2": {"image": "pressure/Ptwopressure.webp", "points": 3},
    "P2*": {"image": "pressure/Ptwodpressure.webp", "points": 3},
    "P3": {"image": "pressure/Pthreepressure.webp", "points": 4},
    "P3*": {"image": "pressure/Pthreedpressure.webp", "points": 4},
    "None": {"image": "pressure/emptypressure.webp", "points": 0},
}

velocity_cards = {
    "P1": {"image": "velocity/Ponevel.webp", "points": 4},
    "P1*": {"image": "velocity/Ponedvel.webp", "points": 4},
    "BDM1": {"image": "velocity/BDMonevel.webp", "points": 4},
    "Crouzeix-Raviart": {"image": "velocity/CRvel.webp", "points": 4},
    "P2": {"image": "velocity/Ptwovel.webp", "points": 3},
    "P2*": {"image": "velocity/Ptwodvel.webp", "points": 3},
    "BDM2": {"image": "velocity/BDMtwovel.webp", "points": 3},
    "P3": {"image": "velocity/Pthreevel.webp", "points": 2},
    "P3*": {"image": "velocity/Pthreedvel.webp", "points": 2},
    "BDM3": {"image": "velocity/BDMthreevel.webp", "points": 2},
    "BDM4": {"image": "velocity/BDMfourvel.webp", "points": 1},
    "P4": {"image": "velocity/Pfourvel.webp", "points": 1},
    "P4*": {"image": "velocity/Pfourdvel.webp", "points": 1},
    "None": {"image": "velocity/emptyvel.webp", "points": 0},
}

extra_cards = {
    "Interior Penalty": {"image": "extra/ipdg.webp", "points": 0},
    "Pressure-Jump": {"image": "extra/pj.webp", "points": -1},
    "Powell-Sabin Split": {"image": "extra/psmesh.webp", "points": -1},
    "Alfeld Split": {"image": "extra/alfeldsplit.webp", "points": -1},
    "Brezzi-Pitkäranta": {"image": "extra/bp.webp", "points": -2},
    "P3 Bubble": {"image": "extra/Pthreebubble.webp", "points": -1},
    "None": {"image": "extra/emptyextra.webp", "points": 0},
}


class CardSelector(QCard):
    def __init__(self, options, label):
        self._options = options
        self.selector = QSelect(
            options=list(options.keys()), model_value="None", label=label
        )
        self.selector.on_update_model_value(self.update)
        self.div_image = QImg(
            src=image(options[self.selector.model_value]["image"]), width="200px"
        )
        super().__init__(
            self.selector, self.div_image, style="padding: 10px; margin: 10px;"
        )

    def update(self):
        print("selected item =", self.selector.model_value)
        self.div_image.src = image(self._options[self.selector.model_value]["image"])

    def on_update_model_value(self, callback):
        self.selector.on_update_model_value(callback)

    @property
    def model_value(self):
        return self.selector.model_value

    @property
    def points(self):
        try: 
            return self._options[self.selector.model_value]["points"]
        except:
            return 0

    @model_value.setter
    def model_value(self, value):
        self.selector.model_value = value


class FeStokesRePair(App):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mesh = CardSelector(
            label="Mesh",
            options=mesh_cards,
        )

        # self.mesh.on_update_model_value(self.calculate)
        self.pressure = CardSelector(
            label="Pressure",
            options=pressure_cards,
        )
        # self.pressure.on_update_model_value(self.calculate)
        self.velocity = CardSelector(
            label="Velocity",
            options=velocity_cards,
        )

        #self.mesh.model_value = "Unstructured Mesh"
        #self.pressure.model_value = "P1"
        #self.velocity.model_value = "P2"

        # self.velocity.on_update_model_value(self.calculate)
        self.add_extra = Row(
            QBtn(round=True, icon="add", fab=True).on_click(self._add_extra),
            classes="items-center",
        )
        self.clear_btn = QBtn(label="Clear").on_click(self.clear)
        self.calc_btn = QBtn(label="Validate").on_click(self.calculate)
        self.bpoints_lbl = Label("Basic points:", classes="text-h6 q-mt-md")
        self.bpoints_dsp = Label(" -?- ", classes="text-h6 q-mt-md")
        self.optconv_lbl = Label("Optimal convergence:", classes="text-h6 q-mt-md")
        self.optconv_dsp = Label(" -?- ", classes="text-h6 q-mt-md")
        self.prrob_lbl = Label("Pressure robustness:", classes="text-h6 q-mt-md")
        self.prrob_dsp = Label(" -?- ", classes="text-h6 q-mt-md")

        self.totpoints_lbl = Label("Total:", classes="text-h6 q-mt-md")
        self.totpoint_dsp = Label(" -?- ", classes="text-h6 q-mt-md")
        self.is_stable = False

        self.extras = Row()
        self.velocity_sol = SolutionWebgui(
            caption="Velocity", show_clipping=False, show_view=False
        )
        self.pressure_sol = SolutionWebgui(
            caption="Pressure", show_clipping=False, show_view=False
        )
        self.convergence_plot = PlotlyComponent(id="convergence_plot")
        self.user_warning = UserWarning(
            title="Error in calculation!", message="Pairing does not seem to work"
        )

        self.cards = Row(
            self.mesh, self.pressure, self.velocity, self.extras, self.add_extra
        )
        self.computing = QInnerLoading(
            QSpinnerGears(size="100px", color="primary"),
            Centered("Calculating..."),
            showing=True,
            style="z-index:100;",
        )
        self.computing.hidden = True

        self.result_section = Row(
            self.computing,
            Col(Heading("Velocity", level=3), self.velocity_sol),
            Col(Heading("Pressure", level=3), self.pressure_sol),
            Col(self.convergence_plot),
        )
        self.component = Centered(
            Col(
                self.user_warning,
                self.cards,
                Row(self.clear_btn, self.calc_btn, 
                    QSeparator(spaced=True, vertical=True), self.bpoints_lbl, self.bpoints_dsp,
                    QSeparator(spaced=True, vertical=True), self.optconv_lbl, self.optconv_dsp,
                    QSeparator(spaced=True, vertical=True), self.prrob_lbl, self.prrob_dsp,
                    
                    QSeparator(spaced=True, vertical=True), self.totpoints_lbl, self.totpoint_dsp),
                self.result_section,
                classes="q-gutter-lg q-ma-lg",
            )
        )

    def clear(self):
        self.extras.children = []
        self.mesh.model_value = "None"
        self.mesh.update()
        self.pressure.model_value = "None"
        self.pressure.update()
        self.velocity.model_value = "None"
        self.velocity.update()
        self.velocity_sol._webgui.clear()
        self.pressure_sol._webgui.clear()
        import plotly.graph_objects as go
        self.fig = fig = go.Figure(layout = {"title": "Convergence", "font" : {"size": 18}})
        fig.update_xaxes(title="Refinement level")
        fig.update_yaxes(title="Error", type="log")
        fig.update_layout(
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(r=10),
        )
        self.convergence_plot.draw(self.fig)
        self.bpoints_dsp.text = " -?- "
        self.is_stable = False

    def _add_extra(self):
        i = len(self.extras.children)
        extra = CardSelector(
            label="Extra " + str(i + 1),
            options=extra_cards,
        )
        # extra.on_update_model_value(self.calculate)
        self.extras.children = self.extras.children + [extra]

    def calculate(self):
        if self.mesh.model_value is None:
            return
        self.computing.hidden = False
        mesh = self._create_mesh()
        if self.velocity.model_value is None or self.pressure.model_value is None:
            self.velocity_sol.draw(mesh)
            self.pressure_sol.draw(mesh)
            self.computing.hidden = True
            return
        try:
            self._solve_stokes_n()
        except Exception as e:
            print("caught exception", e)
            self.user_warning.message = str(e)
            self.user_warning.show()
            self.velocity_sol._webgui.clear()
            self.pressure_sol._webgui.clear()
        self.computing.hidden = True

        bpoints = 0
        bpoints += self.mesh.points
        bpoints += self.pressure.points
        bpoints += self.velocity.points
        for e in self.extras.children:
            bpoints += e.points

        self.bpoints_dsp.text = str(bpoints)
            

        totpoints = 0
        totpoints += bpoints
        # if self.optconv_dsp can be converted to int, add it
        try:
            totpoints += int(self.optconv_dsp.text)
        except:
            pass

        try:
            totpoints += int(self.prrob_dsp.text)
        except:
            pass
        
        if self.is_stable:
            self.totpoint_dsp.text = str(totpoints)
        else: 
            self.totpoint_dsp.text = "Unstable 0 !"
        

    def _create_mesh(self, ref_lvl=0):
        import ngsolve.meshes as ngs_meshes
        from math import pi
        print("Create mesh")
        self.uexact = ngs.CF((ngs.sin(pi*ngs.x)*ngs.cos(pi*ngs.y), -ngs.cos(pi*ngs.x)*ngs.sin(pi*ngs.y)))
        self.uexactbnd = self.uexact
        self.pexact = ngs.sin(pi*ngs.x)*ngs.cos(pi*ngs.y)         

        if self.mesh.model_value == "Unstructured Mesh":
            geo = ngocc.unit_square
            mesh = ngs.Mesh(geo.GenerateMesh(maxh=0.25))
            if ref_lvl > 0:
                for _ in range(ref_lvl):
                    mesh.ngmesh.Refine()
        elif self.mesh.model_value == "Curved Mesh":
            shape = ngocc.Circle((0., 0.), 1).Face()
            shape.edges.name = "bnd"
            geo = ngocc.OCCGeometry(shape, dim=2)
            mesh = ngs.Mesh(geo.GenerateMesh(maxh=1))

            r = ngs.sqrt(ngs.x**2 + ngs.y**2)
            self.uexact = ngs.CF((ngs.cos(0.5*pi*r)*ngs.y, -ngs.cos(0.5*pi*r)*ngs.x))
            self.uexactbnd = ngs.CF((0,0))
            self.pexact = ngs.sin(pi*ngs.x)*ngs.cos(pi*ngs.y)         

            if ref_lvl > 0:
                for _ in range(ref_lvl):
                    mesh.ngmesh.Refine()

        elif self.mesh.model_value == "Type One Mesh":
            mesh = ngs_meshes.MakeStructured2DMesh(quads=False, nx=2**(ref_lvl+1), ny=2**(ref_lvl+1))
        else:  # self.mesh.model_value == "Singular Vertex Mesh":
            mesh = ngs_meshes.MakeStructured2DMesh(quads=True, nx=2**(ref_lvl+1), ny=2**(ref_lvl+1))
            # split quads in 4 trigs?
        for e in self.extras.children:
            if e.model_value == "Alfeld Split":
                mesh.ngmesh.Save("tmp.vol")
                mesh = ngs.Mesh("tmp.vol")
                mesh.ngmesh.Compress()
                ngmesh = mesh.ngmesh
                ngmesh.SplitAlfeld()
                mesh = ngs.Mesh(ngmesh)
            elif e.model_value == "Powell-Sabin Split":
                mesh.ngmesh.Save("tmp.vol")
                mesh = ngs.Mesh("tmp.vol")
                mesh.ngmesh.Compress()
                ngmesh = mesh.ngmesh
                ngmesh.SplitPowellSabin()
                mesh = ngs.Mesh(ngmesh)
        if self.mesh.model_value == "Curved Mesh":
            mesh.Curve(5)


        self.graduexact = ngs.CF((self.uexact[0].Diff(ngs.x),self.uexact[0].Diff(ngs.y),                    
                                  self.uexact[1].Diff(ngs.x),self.uexact[1].Diff(ngs.y)),dims=(2,2))
        self.m_nu_lap_u_exact = ngs.CF((- self.uexact[0].Diff(ngs.x).Diff(ngs.x) - self.uexact[0].Diff(ngs.y).Diff(ngs.y),
                    - self.uexact[1].Diff(ngs.x).Diff(ngs.x) - self.uexact[1].Diff(ngs.y).Diff(ngs.y)))
        self.nabla_p_exact = ngs.CF((self.pexact.Diff(ngs.x), self.pexact.Diff(ngs.y)))

        return mesh


    def _solve_stokes(self, mesh):
        assert self.velocity.model_value is not None
        assert self.pressure.model_value is not None
        print("Create Velocity space")
        extras = [e.model_value for e in self.extras.children]
        if ("Interior Penalty" in extras) or ("Pressure-Jump" in extras):
            dgjumps = True
        else:
            dgjumps = False
        if self.velocity.model_value == "Crouzeix-Raviart":
            print("Create Crouzeix-Raviart")
            V = ngs.FESpace("nonconforming", mesh, order=1, dirichlet=".*",
                            dgjumps=dgjumps) ** 2
        elif self.velocity.model_value.startswith("BDM"):
            print("Create BDM of order", self.velocity.model_value[-1])
            V = ngs.HDiv(mesh, order=int(self.velocity.model_value[-1]),
                         dgjumps=dgjumps)
        else:
            order = int(self.velocity.model_value[1])
            print("Create P", order)
            if self.velocity.model_value.endswith("*")  or self.velocity.model_value.endswith("0") :
                print("Create P", order, "DG")
                V = ngs.VectorL2(mesh, order=order, dgjumps=dgjumps)
            else:
                print("Create P", order, "CG")
                V = ngs.VectorH1(mesh, order=order, dgjumps=dgjumps,
                                 dirichlet=".*")
        bubble_space = False
        order_velocity=int(self.velocity.model_value[-1])
        if "P3 Bubble" in extras and order_velocity < 3:
            bubble_space = True
            print("Add P3 Bubble")
            Vhs = ngs.VectorH1(mesh, order=3)
            bubbles = ngs.BitArray(Vhs.ndof)
            bubbles.Clear()
            for el in Vhs.Elements(ngs.VOL):
                dofs = Vhs.GetDofNrs(ngs.NodeId(ngs.CELL, el.nr))
                bubbles.Set(dofs[0])
            Vhb = ngs.Compress(Vhs, active_dofs=bubbles)
            V *= Vhb
        print("Create Pressure space")
        if self.pressure.model_value.endswith("*") or self.pressure.model_value.endswith("0"):
            print(f"Create L2({int(self.pressure.model_value[1])})")
            Q = ngs.L2(mesh, order=int(self.pressure.model_value[1]))
        else:
            print(f"Create H1({int(self.pressure.model_value[1])})")
            Q = ngs.H1(mesh, order=int(self.pressure.model_value[1]))
        fes = V * Q
        if bubble_space:
            print("in bubble space")
            (us, ub, p), (vs, vb, q) = fes.TnT()
            gradu = ngs.Grad(us) + ngs.Grad(ub)
            gradv = ngs.Grad(vs) + ngs.Grad(vb)
            divu = ngs.div(us) + ngs.div(ub)
            divv = ngs.div(vs) + ngs.div(vb)
            uOther, vOther = us.Other() + ub.Other(), vs.Other() + vb.Other()
            graduOther, gradvOther = ngs.Grad(us.Other())+ngs.Grad(ub.Other()), ngs.Grad(vs.Other())+ngs.Grad(vb.Other())
            u, v = us + ub, vs + vb
        else:
            (u, p), (v, q) = fes.TnT()
            gradu, gradv = ngs.Grad(u), ngs.Grad(v)
            divu, divv = ngs.div(u), ngs.div(v)
            uOther, vOther = u.Other(), v.Other()
            graduOther, gradvOther = ngs.Grad(u.Other()), ngs.Grad(v.Other())


        stokes = (
            ngs.InnerProduct(gradu, gradv) * ngs.dx
            - divu * q * ngs.dx
            - divv * p * ngs.dx
            - 1e-8 * p * q * ngs.dx  # to allow for sparsecholesky
        )

        def avg(u):
            return 0.5 * (u.Other() + u)
        def jump(u):
            return u - u.Other()
        a = ngs.BilinearForm(stokes)
        f = ngs.LinearForm((self.m_nu_lap_u_exact + self.nabla_p_exact)*v*ngs.dx)
        n = ngs.specialcf.normal(mesh.dim)
        h = ngs.specialcf.mesh_size
        if "Interior Penalty" in extras:
            k = V.globalorder
            a += 0.5*(-gradu*n-graduOther*n) * (v-vOther) * ngs.dx(skeleton=True)
            a += 0.5*(-gradv*n-gradvOther*n) * (u-uOther) * ngs.dx(skeleton=True)
            a += avg(p) * (v-vOther) * n * ngs.dx(skeleton=True)
            a += avg(q) * (u-uOther) * n * ngs.dx(skeleton=True)
            a += 20* (k+1)**2 / h * (u-uOther) * (v-vOther) * ngs.dx(skeleton=True)
            a += -gradu*n * v * ngs.ds(skeleton=True)
            a += -gradv*n * u * ngs.ds(skeleton=True)
            a += p*n * v * ngs.ds(skeleton=True)
            a += q*n * u * ngs.ds(skeleton=True)
            a += 20* (k+1)**2 / h * u * v * ngs.ds(skeleton=True)

            f += -gradv*n * self.uexactbnd * ngs.ds(skeleton=True)
            f += q*n * self.uexactbnd * ngs.ds(skeleton=True)
            f += 20* (k+1)**2 / h * self.uexactbnd * v * ngs.ds(skeleton=True)

        if "graddiv" in extras:
            a += 1e3 * divu * divv * ngs.dx
            a += 1e3 * u*n * v*n * ngs.dx(skeleton=True)
        if "Brezzi-Pitkäranta" in extras:
            a += -h**2 * ngs.grad(p) * ngs.grad(q) * ngs.dx
        if "Pressure-Jump" in extras:
            a += -h * jump(p) * jump(q) * ngs.dx(skeleton=True)




        a.Assemble()
        f.Assemble()
        gf = ngs.GridFunction(fes)
        if bubble_space:
            gfu, gfb, gfp = gf.components
            vel = gfu + gfb
            gradvel = ngs.Grad(gfu) + ngs.Grad(gfb)
            divuh = ngs.div(gfu) + ngs.div(gfb)
        else:
            gfu, gfp = gf.components
            vel = gfu
            gradvel = ngs.Grad(gfu)
            divuh = ngs.div(gfu)
        #uin = ngs.CF((1.5 * 4 * ngs.y * (0.41 - ngs.y) / (0.41 * 0.41), 0))
        gfu.Set(self.uexactbnd, definedon=mesh.Boundaries(".*"))
        res = (-a.mat * gf.vec).Evaluate()
        res += f.vec
        inv = a.mat.Inverse(inverse="sparsecholesky", freedofs=fes.FreeDofs())
        #inv = ngs.directsolvers.SuperLU(a.mat, fes.FreeDofs())
        gf.vec.data += inv * res

        offset_p = ngs.Integrate(gfp-self.pexact, mesh)/ngs.Integrate(1, mesh)
        p = gfp - offset_p

        return (vel, gradvel, divuh, gfu.space.globalorder), (p, gfp.space.globalorder)

    def _solve_stokes_n(self, nref=4):
        error_v_divl2 = []
        error_v_l2 = []
        error_v_h1semi = []
        error_v_h1semi2 = []
        error_p_l2 = []
        for ref in range(nref):
            mesh = self._create_mesh(ref)
            (vel, gradvel, divuh, velorder), (gfp, porder) = self._solve_stokes(mesh)
            error_v_l2.append(ngs.sqrt(ngs.Integrate((vel-self.uexact)**2, mesh)))
            error_v_h1semi.append(ngs.sqrt(ngs.Integrate(ngs.InnerProduct(gradvel-self.graduexact,gradvel-self.graduexact), mesh)))
            error_v_divl2.append(ngs.sqrt(ngs.Integrate(divuh**2, mesh)))
            error_p_l2.append(ngs.sqrt(ngs.Integrate((gfp-self.pexact)**2, mesh)))
        if nref > 1:
            from math import log
            eoc_v_h1 = log(error_v_h1semi[-1]/error_v_h1semi[-2])/log(0.5)
            eoc_p_l2 = log(error_p_l2[-1]/error_p_l2[-2])/log(0.5)


            opt_rates = True
            convergence = False

            verbose = False
            if eoc_v_h1 - velorder > - 0.25:
                if verbose:
                    print("velocity H1(semi) error optimal")
            else:
                opt_rates = False

            if eoc_v_h1 > 0.25 and eoc_p_l2 > 0.25:
                convergence = True
            else:
                if verbose:
                    print("no convergence")

            if eoc_p_l2 - porder - 1 > - 0.25:
                if verbose:
                    print("pressure L2 error optimal")
            else:
                opt_rates = False

            if opt_rates:
                self.optconv_dsp.text = "2"
            else:
                self.optconv_dsp.text = "0"
        else:
            self.optconv_dsp.text = " -?- "
        
        print(error_p_l2[-1], error_v_l2[-1])
        if error_p_l2[-1]< 1 and error_v_l2[-1] < 1:
            self.is_stable = True

        import plotly.graph_objects as go
        self.fig = fig = go.Figure(layout = {"title": "Convergence", "font" : {"size": 18}})
        fig.update_xaxes(title="Refinement level")
        fig.update_yaxes(title="Error", type="log")
        fig.add_trace(
            go.Scatter(x=list(range(nref)), y=error_v_l2, mode="lines+markers", name="Velocity"))
        fig.add_trace(
            go.Scatter(x=list(range(nref)), y=error_p_l2, mode="lines+markers", name="Pressure"))
        fig.update_layout(
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(r=10),
        )
        self.convergence_plot.draw(self.fig)
        self.velocity_sol.draw(vel, mesh)
        self.pressure_sol.draw(gfp, mesh)
