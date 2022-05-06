"""Module to run Tc calculation."""
# Ref: https://arxiv.org/abs/2205.00060
from jarvis.io.qe.outputs import DataFileSchema
from jarvis.core.atoms import Atoms
from jarvis.core.kpoints import Kpoints3D
from jarvis.tasks.qe.qe import QEjob
import numpy as np
import os
# from jarvis.core.utils import get_factors


def calc_Tc(wlog=300, lamb=1.0, mu=0.1):
    """Calculate Tc."""
    tc = (wlog / 1.2) * np.exp(
        -1.04 * (1 + lamb) / (lamb * (1 - 0.062 * mu) - mu)
    )
    return tc


def parse_lambda(filename="lambda"):
    """Parse lambda file."""
    f = open(filename, "r")
    lines = f.read().splitlines()
    f.close()
    for i in lines:
        if "Broadening" in i:
            tmp = i.split()
            print(i.split())
            wlog = float(tmp[-1])
            lamb = float(tmp[3])
            Tc = calc_Tc(wlog=wlog, lamb=lamb)
            print("Tc", Tc)
            print()


def very_clean():
    """Clean files."""
    cmd = (
        "rm -r elph_dir _ph0 *.dos* *.in *.json  *.fc *.freq* *.save "
        + "*.out *.dyn* *wfc* *.xml  *save lambda *.modes dyn*"
    )
    os.system(cmd)


class SuperCond(object):
    """Module to calculate Tc."""

    def __init__(
        self,
        atoms=None,
        kp=None,
        qp=None,
        qe_cmd="pw.x",
        relax_calc="'vc-relax'",
        pressure=None,
    ):
        """Initialize the class."""
        self.atoms = atoms
        self.kp = kp
        self.qp = qp
        self.relax_calc = relax_calc
        self.qe_cmd = qe_cmd
        self.pressure = pressure

    def to_dict(self):
        """Get dictionary."""
        info = {}
        info["atoms"] = self.atoms.to_dict()
        info["kp"] = self.kp.to_dict()
        info["qp"] = self.qp.to_dict()
        info["qe_cmd"] = self.qe_cmd
        info["relax_calc"] = self.relax_calc
        info["pressure"] = self.pressure
        return info

    @classmethod
    def from_dict(self, info={}):
        """Load from a dictionary."""
        return SuperCond(
            atoms=Atoms.from_dict(info["atoms"]),
            kp=Kpoints3D.from_dict(info["kp"]),
            qp=Kpoints3D.from_dict(info["qp"]),
            qe_cmd=info["qe_cmd"],
            pressure=info["pressure"],
            relax_calc=info["relax_calc"],
        )

    def runjob(self):
        """Calculate Tc using QE."""
        # Still under development,
        atoms = self.atoms
        kp = self.kp
        qp = self.qp
        relax = {
            "control": {
                # "calculation": "'scf'",
                "calculation": self.relax_calc,  # "'vc-relax'",
                "restart_mode": "'from_scratch'",
                "prefix": "'RELAX'",
                "outdir": "'./'",
                "tstress": ".true.",
                "tprnfor": ".true.",
                "disk_io": "'low'",
                "wf_collect": ".true.",
                "pseudo_dir": None,
                "verbosity": "'high'",
                "nstep": 100,
            },
            "system": {
                "ibrav": 0,
                "nat": None,
                "ntyp": None,
                "ecutwfc": 45,
                "ecutrho": 250,
                "q2sigma": 1,
                "ecfixed": 44.5,
                "qcutz": 800,
                "occupations": "'smearing'",
                "degauss": 0.01,
                "lda_plus_u": ".false.",
            },
            "electrons": {
                "diagonalization": "'david'",
                "mixing_mode": "'local-TF'",
                "mixing_beta": 0.3,
                "conv_thr": "1d-9",
            },
            "ions": {"ion_dynamics": "'bfgs'"},
            "cell": {"cell_dynamics": "'bfgs'", "cell_dofree": "'all'"},
        }
        if self.pressure is not None:
            relax["cell"]["press"] = self.pressure
        qejob_relax = QEjob(
            atoms=atoms,
            input_params=relax,
            output_file="relax.out",
            qe_cmd=self.qe_cmd,
            jobname="relax",
            kpoints=kp,
            input_file="arelax.in",
        )

        info = qejob_relax.runjob()
        xml_path = info["xml_path"]
        xml_dat = DataFileSchema(xml_path)
        final_strt = xml_dat.final_structure

        print("final_strt", final_strt)

        # scf_init =
        scf_init = {
            "control": {
                "calculation": "'scf'",
                "restart_mode": "'from_scratch'",
                "prefix": "'QE'",
                "outdir": "'./'",
                "tstress": ".true.",
                "tprnfor": ".true.",
                "disk_io": "'low'",
                "pseudo_dir": None,
                "verbosity": "'high'",
                "nstep": 100,
                "etot_conv_thr": "1.0d-5",
                "forc_conv_thr": "1.0d-4",
            },
            "system": {
                "ibrav": 0,
                "degauss": 0.01,
                "nat": None,
                "ntyp": None,
                "ecutwfc": 45,
                "ecutrho": 250,
                "occupations": "'smearing'",
                "smearing": "'mp'",
                "la2F ": ".true.",
            },
            "electrons": {
                "diagonalization": "'david'",
                "mixing_mode": "'plain'",
                "mixing_beta": 0.7,
                "conv_thr": "1d-9",
            },
        }

        qejob_scf_init = QEjob(
            atoms=final_strt,
            input_params=scf_init,
            output_file="scf_init.out",
            qe_cmd=self.qe_cmd,
            jobname="scf_init",
            kpoints=kp,
            input_file="ascf_init.in",
        )

        info_scf = qejob_scf_init.runjob()
        print(info_scf)
        # kpts = kp._kpoints[0]
        qpts = qp._kpoints[0]
        nq1 = qpts[0]  # get_factors(kpts[0])[0]
        nq2 = qpts[1]  # get_factors(kpts[1])[0]
        nq3 = qpts[2]  # get_factors(kpts[2])[0]
        ph = {
            "inputph": {
                "prefix": "'QE'",
                "fildyn": "'QE.dyn'",
                "outdir": "'./'",
                "ldisp": ".true.",
                "trans": ".true.",
                "fildvscf": "'dvscf'",
                "electron_phonon": "'interpolated'",
                "el_ph_sigma": 0.005,
                "nq1": nq1,
                "nq2": nq2,
                "nq3": nq3,
                "tr2_ph": "1.0d-12",
            }
        }
        qejob_ph = QEjob(
            atoms=final_strt,
            input_params=ph,
            output_file="ph.out",
            qe_cmd=self.qe_cmd.replace("pw.x", "ph.x"),
            jobname="ph",
            kpoints=None,
            input_file="aph.in",
        )

        qejob_ph.runjob()
        # import sys
        # sys.exit()
        qr = {
            "input": {
                "zasr": "'simple'",
                "fildyn": "'QE.dyn'",
                "flfrc": "'QE333.fc'",
                "la2F": ".true.",
            }
        }
        qejob_qr = QEjob(
            atoms=final_strt,
            input_params=qr,
            output_file="q2r.out",
            # qe_cmd="/home/knc6/Software/qe/q-e/bin/q2r.x",
            qe_cmd=self.qe_cmd.replace("pw.x", "q2r.x"),
            jobname="qr",
            kpoints=None,
            input_file="aqr.in",
        )

        qejob_qr.runjob()

        kpts = kp._kpoints[0]
        matdyn = {
            "input": {
                "asr": "'simple'",
                "flfrc": "'QE333.fc'",
                "flfrq": "'QE333.freq'",
                "la2F": ".true.",
                "dos": ".true.",
                "fldos": "'phonon.dos'",
                "nk1": kpts[0],
                "nk2": kpts[1],
                "nk3": kpts[2],
                "ndos": 50,
            }
        }

        qejob_matdyn = QEjob(
            atoms=final_strt,
            input_params=matdyn,
            output_file="matdyn.out",
            # qe_cmd="/home/knc6/Software/qe/q-e/bin/matdyn.x",
            qe_cmd=self.qe_cmd.replace("pw.x", "matdyn.x"),
            jobname="matdyn",
            kpoints=None,
            input_file="amatdyn.in",
        )

        qejob_matdyn.runjob()
        parse_lambda()
