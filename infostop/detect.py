import numpy as np
from infostop import utils

def best_partition(coords, r1=10, r2=10, return_medoid_labels=False, label_singleton=False):
    """Infer best stop-location labels from stationary points using infomap.

    The method entils the following steps:
        1.  Detect which points are stationary and store only the median (lat, lon) of
            each stationarity event. A point belongs to a stationarity event if it is 
            less than `r1` meters away from the median of the time-previous collection
            of stationary points.
        2.  Compute the pairwise distances between all stationarity event medians.
        3.  Construct a network that links nodes (event medians) that are within `r2` m.
        4.  Cluster this network using two-level Infomap.
        5.  Put the labels back info a vector that matches the input data in size.
    
    Input
    -----
        coords : array-like (N, 2)
        r1 : number
            Max distance between time-consecutive points to label them as stationary
        r2 : number
            Max distance between stationary points to form an edge.
        return_medoid_labels : bool
            If True, return labels of median values of stationary events, not `coords`.
        label_singleton: bool
            If True, give stationary locations that was only visited once their own
            label. If False, label them as outliers (-1).

    Output
    ------
        out : array-like (N, )
            Array of labels matching input in length. Non-stationary locations and
            outliers (locations visited only once if `label_singleton == False`) are
            labeled as -1. Detected stop locations are labeled from 0 and up, and
            typically locations with more observations have lower indices.
    """
    # PREPROCESS
    # ----------
    # Time-group points
    groups = utils.group_time_distance(coords, r_C=r1)
    
    # Reduce time-grouped points to their median. Only keep stat. groups (size > 1)
    stat_medoids, medoid_map = utils.get_stationary_medoids(groups, min_size=1)
    
    # Compute their pairwise distances
    pairwise_dist = utils.haversine_pdist(stat_medoids)
    
    # NETWORK
    # -------
    # Construct a network where nodes are stationary location events
    # and edges are formed between nodes if they are within distance `r2`
    c = stat_medoids.shape[0]
    
    # Take edges between points where pairwise distance is < r2
    edges = []
    nodes = set()
    singleton_nodes = set(list(range(c)))
    for i in range(c):
        for j in range(i+1, c):
            piotr_index = int(j + i * c - (i+1) * (i+2) / 2)
            if pairwise_dist[piotr_index] < r2:  # index in `pairwise_dist` is upper triangle. Compute from i,j:
                edges.append((i, j))             # square matrix flattened index of i,j *minus* lower triangle
                nodes.update([i, j])             # (including diagonal) down to i+1.
                singleton_nodes -= set([i, j])                                      

    if len(edges) < 1:
        raise Exception("Found only %d edge(s). Provide longer trajectory or increase `r2`.")
        
    # INFER LABELS
    # ------------
    # Infer the partition with infomap. Partiton has from {node: community, ...}
    partition = utils.infomap_communities(list(nodes), edges)
    
    if label_singleton:
        max_label = max(partition.values())
        partition.update(dict(zip(
            singleton_nodes,
            range(max_label+1, max_label+1+len(singleton_nodes))
        )))

    # Cast the partition as a vector of labels like [community, community, ...]
    labels = np.array([
        partition[n] if n in partition else -1
        for n in range(c)]
    )
    
    # Optionally, just return labels of medians of stationary points
    if return_medoid_labels:
        return labels
    
    # POSTPROCESS
    # -----------
    # Label all the input points and return that label vector
    coord_labels = np.ones(shape=coords.shape[0], dtype=int) * (-1)
    for gid, lab in enumerate(labels):
        coord_labels[medoid_map == gid] = lab
    
    return coord_labels