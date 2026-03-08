
import distance  # pyright: ignore[reportMissingImports]
import numpy as np
from collections.abc import Sequence


def check_box(box: Sequence[int]):
    """Checks if the box is legal.

    Args:
        box (tuple[int]): (x_min, y_min, x_max, y_max).

    Raises:
        ValueError: If the coordinates of bottom right point are less than 0
        or input box does not follow (x_min, y_min, x_max, y_max) format.
    """
    # Unpack box
    x1, y1, x2, y2 = box
    if x2 < 0 or y2 < 0:
        raise ValueError(
            "The coordinates of bottom right point must be not less than 0"
        )
    if x1 > x2 or y1 > y2:
        raise ValueError("Input box must be (x_min, y_min, x_max, y_max).")


def calc_box_area(box: Sequence[int]) -> int:
    """Calculates the area of the box.

    Args:
        box (tuple[int]): (x_min, y_min, x_max, y_max).

    Returns:
        int: The area of the box.
    """
    # Check if the box is legal.
    check_box(box)
    # Unpack box
    x1, y1, x2, y2 = box
    return (x2 - x1 + 1) * (y2 - y1 + 1)


def calc_intersection(box_a: Sequence[int], box_b: Sequence[int]) -> tuple[int, int, int, int] | None:
    """Calculates the intersection.

    Args:
        box_a (tuple[int]): (x_min, y_min, x_max, y_max).
        box_b (tuple[int]): (x_min, y_min, x_max, y_max).

    Returns:
        intersection ((tuple[int]) | None): (x_min, y_min, x_max, y_max)
            if exists else None.
    """
    # Check if the box a is legal.
    check_box(box_a)
    # Unpack box a
    a_x1, a_y1, a_x2, a_y2 = box_a
    # Check if the box b is legal.
    check_box(box_b)
    # Unpack box b
    b_x1, b_y1, b_x2, b_y2 = box_b
    # Figure out intersection
    i_x1 = max(a_x1, b_x1)
    i_y1 = max(a_y1, b_y1)
    i_x2 = min(a_x2, b_x2)
    i_y2 = min(a_y2, b_y2)
    # Calculate intersection
    intersection = None
    if i_x1 <= i_x2 and i_y1 <= i_y2:
        intersection = (i_x1, i_y1, i_x2, i_y2)
    return intersection


def calc_iou(box_a: Sequence[int], box_b: Sequence[int]) -> float:
    """Calculates the intersection over union.

    Args:
        box_a (tuple[int]): (x_min, y_min, x_max, y_max).
        box_b (tuple[int]): (x_min, y_min, x_max, y_max).

    Returns:
        iou (float): The intersection over union.
    """
    # Figure out intersection
    # Get the intersection range of two boxes
    intersection = calc_intersection(box_a, box_b)
    # Calculate intersection over union
    iou = 0.0
    if intersection is not None:
        # Get the area of box a
        a_area = calc_box_area(box_a)
        # Get the area of box b
        b_area = calc_box_area(box_b)
        # Get the area of intersection box
        i_area = calc_box_area(intersection)
        # Calculate the ratio of intersection area to total area of a and b.
        # Subtract intersection area once since it's counted twice in the sum.
        iou = i_area / (a_area + b_area - i_area)
    return iou


def calc_ioa(box_a: Sequence[int], box_b: Sequence[int]) -> float:
    """Calculates the intersection over box a.

    Args:
        box_a (tuple[int]): (x_min, y_min, x_max, y_max).
        box_b (tuple[int]): (x_min, y_min, x_max, y_max).

    Returns:
        ioa (float): The intersection over box a.
    """
    # Figure out intersection
    intersection = calc_intersection(box_a, box_b)
    # Calculate intersection over box a
    ioa = 0.0
    if intersection is not None:
        a_area = calc_box_area(box_a)
        i_area = calc_box_area(intersection)
        ioa = i_area / a_area
    return ioa


def calc_bbox(polygon: list[int]) -> tuple[int, int, int, int]:
    """Calculates bounding box based on polygon.

    Args:
        polygon (list[int]): [x1, y1, x2, y2, ...].

    Returns:
        tuple[int] : (x_min, y_min, x_max, y_max)
    """
    x_min = min(polygon[::2])
    y_min = min(polygon[1::2])
    x_max = max(polygon[::2])
    y_max = max(polygon[1::2])
    return x_min, y_min, x_max, y_max


def cal_euclidean_distance(
    feature_a: list[float] | np.ndarray, feature_b: list[float] | np.ndarray
) -> float:
    """Calculate the euclidean distance between feature a and b.

    Args:
        feature_a (list[float] | np.array): the embedding vector of feature a.
        feature_b (list[float] | np.array): the embedding vector of feature b.
    """

    feat_np_a = np.array(feature_a)
    feat_np_b = np.array(feature_b)

    return float(np.linalg.norm(feat_np_a - feat_np_b))


def cal_cosine_distance(
    feature_a: list[float] | np.ndarray, feature_b: list[float] | np.ndarray
) -> float:
    """Calculate the cosine distance between feature a and b.

    Args:
        feature_a (list[float] | np.array): the embedding vector of feature a.
        feature_b (list[float] | np.array): the embedding vector of feature b.
    """

    feat_np_a = np.array(feature_a)
    feat_np_b = np.array(feature_b)
    eps = 1e-6
    cosine_similarity = np.dot(feat_np_a, feat_np_b) / (
        np.linalg.norm(feat_np_a) * np.linalg.norm(feat_np_b) + eps
    )

    return 1 - (cosine_similarity + 1) / 2


def calc_piecewise(
    x: float, x1: float = 0.5, y1: float = 0.6, reverse: bool = False
) -> float:
    """Calculates a two-stage linear piecewise function.

    The function is used for calculating a special two-stage linear piecewise
    function which domain and range are limited in [0,1].

    Args:
        x (float): The independent variable.
        x1 (float, optional): The x value of dividing point. Defaults to 0.5.
        y1 (float, optional): The y value of dividing point. Defaults to 0.6.
        reverse (bool, optional): The direction of the piecewise function.
            If False, the function is increasing, otherwise, decreasing.
            Defaults to False.

    Raises:
        ValueError: If the coordinate of dividing point (x1, y1) is
            out of range.
        ValueError: If the independent variable is out of range.

    Returns:
        float: The function value from piecewise function.
    """
    if not (0.0 <= x1 <= 1.0 and 0.0 <= y1 <= 1.0):
        raise ValueError("x1 and y1 must be in [0, 1.0].")
    if not 0.0 <= x <= 1.0:
        raise ValueError("independent variable x must be in [0, 1.0].")
    if reverse:
        y0, y2 = 1.0, 0.0
    else:
        y0, y2 = 0.0, 1.0
    eps = 1e-6
    k1 = (y1 - y0) / (x1 + eps)
    k2 = (y2 - y1) / (1 - x1 + eps)
    return np.piecewise(  # pyright: ignore[reportReturnType]
        x, [x <= x1, x > x1], [lambda x: y0 + k1 * x, lambda x: y1 + k2 * (x - x1)]  # pyright: ignore[reportOperatorIssue]
    )


def calc_text_similarity(s1: str, s2: str, method: str = "jaccard") -> float:
    """Calculates two sentence similarity, all score will be scaled to 0~1.

    Args:
        s1 (str): Fisrt sentence.
        s2 (str): Second sentence.
        method (str, optional): The compute method. Defaults to 'jaccard'.

    Raises:
        KeyError: Wrong method name.

    Returns:
        float: The similarity score. To keep the score uniformity, the score
            will be scaled to 0~1 and 1 means the two sentence are the same.
    """
    if method == "jaccard":
        similarity = 1 - distance.jaccard(s1, s2)
    elif method == "nlevenshtein":
        similarity = 1 - distance.nlevenshtein(s1, s2)
    else:
        # TODO: add more methods
        raise KeyError("No this method")
    return similarity
