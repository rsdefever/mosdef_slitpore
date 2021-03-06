import signac
import unyt as u
import numpy as np
import pandas as pd

from mosdef_cassandra.analysis import ThermoProps


def main():

    pore_area = 2 * 29.472 * 29.777 * u.angstrom**2

    project = signac.get_project("../")
    mus = []
    nmols = []
    runs = []
    for job in project:
        runs.append(job.sp.run)
        mus.append(job.sp.mu * u.kJ/u.mol)
        thermo = ThermoProps(job.fn("gcmc.out.prp"))
        nmols.append(thermo.prop("Nmols_2", start=200000000).mean())

    mus = u.unyt_array(mus * u.kJ/u.mol)
    nmols = np.asarray(nmols)
    runs = np.asarray(runs)
    df = pd.DataFrame(
        columns=["mu-cassandra_kJmol", "run", "nmols_per_nm^2"]
    )
    df["mu-cassandra_kJmol"] = mus.to_value("kJ/mol")
    df["run"] = runs
    df["nmols"] = nmols
    df["nmols_per_nm^2"] = nmols / pore_area.to_value(u.nm**2)
    df.to_csv("results.csv")


if __name__ == "__main__":
    main()
