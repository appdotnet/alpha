def fit_to_box(w, h, max_w, max_h, expand=False):
    # proportionately scale a box defined by (w,h) so that it fits within a box defined by (max_w, max_h)
    # by default, only scaling down is allowed, unless expand=True, in which case scaling up is allowed
    if w < max_w and h < max_h and not expand:
        return (w, h)
    largest_ratio = max(float(w) / max_w, float(h) / max_h)
    new_height = int(float(h) / largest_ratio)
    new_width = int(float(w) / largest_ratio)
    return (new_width, new_height)
