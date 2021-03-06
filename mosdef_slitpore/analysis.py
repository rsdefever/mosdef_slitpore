import numpy as np


def compute_density(
    traj,
    area,
    surface_normal_dim=2,
    pore_center=0.0,
    max_distance=1.0,
    bin_width=0.01,
    symmetrize=False,
):
    """Compute the density of traj in atoms/nm^3

    Parameters
    ----------
    traj : mdtraj.Trajectory,
        trajectory to analyze
    area : float
        area of the surface in nm^2
    surface_normal_dim : enum (0,1,2), optional, default = 2
        direction normal to the surface (x:0, y:1, z:2)
    pore_center : float, optional, default = 0.0
        coordinate of the pore center along surface_normal_dim
    max_distance : float, optional, default = 1.0
        max distance to consider from the center of the pore
    bin_width : float, optional, default = 0.01
        width of the bin for computing s
    symmetrize : bool, optional, default = False
        if binning should be done in abs(z) instead of z
    Returns
    -------
    bin_centers : np.ndarray
        the bin centers, shifted so that pore_center is at 0.0
    density : np.ndarray
        the density (atoms / nm^3) in each bin
    """
    if symmetrize:
        distances = abs(traj.xyz[:, :, surface_normal_dim] - pore_center)
    else:
        distances = traj.xyz[:, :, surface_normal_dim] - pore_center
    bin_centers = []
    density = []
    for bin_center in np.arange(-max_distance, max_distance, bin_width):
        mask = np.logical_and(
            distances > bin_center - 0.5 * bin_width,
            distances < bin_center + 0.5 * bin_width,
        )
        bin_centers.append(bin_center)
        if symmetrize:
            if np.isclose(bin_center, 0):
                density.append(mask.sum() / (area * 1 * bin_width * traj.n_frames))
            else:
                density.append(mask.sum() / (area * 2 * bin_width * traj.n_frames))
        else:
            density.append(mask.sum() / (area * bin_width * traj.n_frames))

    return bin_centers, density


def compute_s(
    traj,
    surface_normal_dim=2,
    pore_center=0.0,
    max_distance=1.0,
    bin_width=0.01,
    bond_array=None,
    symmetrize=False,
):

    """Compute the "s" order parameter

    Parameters
    ----------
    traj : mdtraj.Trajectory,
        trajectory to analyze
    surface_normal_dim : enum (0,1,2), optional, default = 2
        direction normal to the surface (x:0, y:1, z:2)
    pore_center : float, optional, default = 0.0
        coordinate of the pore center along surface_normal_dim
    max_distance : float, optional, default = 1.0
        max distance to consider from the center of the pore
    bin_width : float, optional, default = 0.01
        width of the bin for computing
    bond_array : np.array(dtype=np.int32), optional, default = None
        Array of bonds to pass into `make_molecules_whole`
        Warning: This argument is necessary if loading in a mol2 file due to a
        current bug in the MDTraj MOL2 reader: https://github.com/mdtraj/mdtraj/issues/1581
    symmetrize : bool, optional, default = False
        if binning should be done in abs(z) instead of z

    Returns
    -------
    bin_centers : np.ndarray
        the bin centers, shifted so that pore_center is at 0.0
    s_values : np.ndarray
        the value of s for each bin
    """
    # Make molecules whole first
    traj.make_molecules_whole(inplace=True, sorted_bonds=bond_array)
    # Select ow and hw
    water_o = traj.top.select("water and name O")
    water_h = traj.top.select("water and name H")
    traj_ow = traj.atom_slice(water_o)
    traj_hw = traj.atom_slice(water_h)

    # Compute angles between surface normal ([0,0,1]) and h-o-h bisector
    hw_midpoints = traj_hw.xyz.reshape(traj_hw.n_frames, -1, 2, 3).mean(axis=2)
    vectors = traj_ow.xyz - hw_midpoints
    vectors /= np.linalg.norm(vectors, axis=-1, keepdims=True)
    cos_angles = vectors[:, :, surface_normal_dim]

    # Compute distances -- center of pore already @ 0,0; use OW position
    if symmetrize:
        distances = abs(traj_ow.xyz[:, :, surface_normal_dim] - pore_center)
    else:
        distances = traj_ow.xyz[:, :, surface_normal_dim] - pore_center
    bin_centers = []
    s_values = []
    for bin_center in np.arange(-max_distance, max_distance, bin_width):
        mask = np.logical_and(
            distances > bin_center - 0.5 * bin_width,
            distances < bin_center + 0.5 * bin_width,
        )
        s = (3.0 * np.mean(cos_angles[mask] ** 2) - 1.0) / 2.0
        bin_centers.append(bin_center)
        s_values.append(s)

    return bin_centers, s_values


def compute_mol_per_area(
    traj, area, dim, box_range, n_bins, shift=True, frame_range=None
):
    """
    Calculate molecules per area
    Parameters
    ----------
    traj : mdtraj.trajectory
        Trajectory
    area : int or float
        Area of box in dimensions where number density isn't calculated
    dim : int
        Dimension to calculate number density profile (x: 0, y: 1, z: 2)
    box_range : array
        Range of coordinates in 'dim' to evaluate
    n_bins : int
        Number of bins in histogram
    shift : boolean, default=True
        Shift center to zero if True
    frame_range : Python range() (optional)
        Range of frames to calculate number density function over

    Returns
    -------
    areas : list
        A list containing number density for each bin
    new_bins : list
        A list of bins
    """
    water_o = traj.atom_slice(traj.topology.select("name O"))
    resnames = np.unique([x.name for x in water_o.topology.residues])

    if frame_range:
        water_o = water_o[frame_range]
    for i, frame in enumerate(water_o):
        indices = [
            [atom.index for atom in compound.atoms]
            for compound in list(frame.topology.residues)
        ]

        if frame_range:
            if i == 0:
                x = np.histogram(
                    frame.xyz[0, indices, dim].flatten(),
                    bins=n_bins,
                    range=(box_range[0], box_range[1]),
                )
                areas = x[0]
                bins = x[1]
            else:
                areas += np.histogram(
                    frame.xyz[0, indices, dim].flatten(),
                    bins=n_bins,
                    range=(box_range[0], box_range[1]),
                )[0]
        else:
            if i == 0:
                x = np.histogram(
                    frame.xyz[0, indices, dim].flatten(),
                    bins=n_bins,
                    range=(box_range[0], box_range[1]),
                )
                areas = x[0]
                bins = x[1]
            else:
                areas += np.histogram(
                    frame.xyz[0, indices, dim].flatten(),
                    bins=n_bins,
                    range=(box_range[0], box_range[1]),
                )[0]

    areas = np.divide(areas, water_o.n_frames)

    new_bins = list()
    for idx, bi in enumerate(bins):
        if (idx + 1) >= len(bins):
            continue
        mid = (bins[idx] + bins[idx + 1]) / 2
        new_bins.append(mid)

    if shift:
        middle = float(n_bins / 2)
        if middle % 2 != 0:
            shift_value = new_bins[int(middle - 0.5)]
        else:
            shift_value = new_bins[int(middle)]
        new_bins = [(bi - shift_value) for bi in new_bins]

    return (areas, new_bins)


def compute_angle(
    traj,
    surface_normal_dim=2,
    pore_center=0.0,
    max_distance=1.0,
    bin_width=0.01,
    symmetrize=False,
    bond_array=None,
):
    """Compute the cos(angle) between HOH bisector and graphene surface normal

    Parameters
    ----------
    traj : mdtraj.Trajectory,
        trajectory to analyze
    surface_normal_dim : enum (0,1,2), optional, default = 2
        direction normal to the surface (x:0, y:1, z:2)
    pore_center : float, optional, default = 0.0
        coordinate of the pore center along surface_normal_dim
    max_distance : float, optional, default = 1.0
        max distance to consider from the center of the pore
    bin_width : float, optional, default = 0.01
        width of the bin for computing s
    symmetrize : bool, optional, default = False
        if binning should be done in abs(z) instead of z
    bond_array : np.array(dtype=np.int32), optional, default = None
        Array of bonds to pass into `make_molecules_whole`
        Warning: This argument is necessary if loading in a mol2 file due to a
        current bug in the MDTraj MOL2 reader: https://github.com/mdtraj/mdtraj/issues/1581
    Returns
    -------
    bin_centers : np.ndarray
        the bin centers, shifted so that pore_center is at 0.0
    cos_angle_values : np.ndarray
        the value of average cos(angle) for each bin
    cos_angles: np.ndarray
        array that contains all the samples for cos(angle)
    """
    # Make molecules whole first
    traj.make_molecules_whole(inplace=True, sorted_bonds=bond_array)
    # Select ow and hw
    water_o = traj.top.select("water and name O")
    water_h = traj.top.select("water and name H")
    traj_ow = traj.atom_slice(water_o)
    traj_hw = traj.atom_slice(water_h)

    # Compute angles between surface normal ([0,0,1]/[0,0,-1]) and h-o-h bisector
    hw_midpoints = traj_hw.xyz.reshape(traj_hw.n_frames, -1, 2, 3).mean(axis=2)

    vectors = traj_ow.xyz - hw_midpoints
    vectors /= np.linalg.norm(vectors, axis=-1, keepdims=True)
    cos_angles = vectors[:, :, surface_normal_dim]
    # The surface normal is decided by looking at the position of O in H2O
    side_of_pore = np.sign(-traj_ow.xyz[:, :, surface_normal_dim] + pore_center)
    cos_angles = np.multiply(cos_angles, side_of_pore)
    # Compute distances -- center of pore already @ 0,0; use OW position
    if symmetrize:
        distances = abs(traj_ow.xyz[:, :, surface_normal_dim] - pore_center)
    else:
        distances = traj_ow.xyz[:, :, surface_normal_dim] - pore_center
    bin_centers = []
    cos_angle_values = []
    for bin_center in np.arange(-max_distance, max_distance, bin_width):
        mask = np.logical_and(
            distances > bin_center - 0.5 * bin_width,
            distances < bin_center + 0.5 * bin_width,
        )
        cos_angle = np.mean(cos_angles[mask])
        bin_centers.append(bin_center)
        cos_angle_values.append(cos_angle)

    return bin_centers, cos_angle_values, cos_angles
