# -*- coding: utf-8 -*-
import cv2  # pyright: ignore[reportMissingImports]
import matplotlib  # pyright: ignore[reportMissingImports]
import numpy as np


def draw_box(img, box, color):
    """Draws a box on the original image instead of a copy.

    Args:
        img: Original image.
        box: (x_min, y_min, x_max, y_max).
        color: (b, g, r).
    """
    # Unpack box
    x_min, y_min, x_max, y_max = box
    # Assemble upper-left point and bottom tight point
    upper_left_point = (int(x_min + 0.5), int(y_min + 0.5))
    bottom_right_point = (int(x_max + 0.5), int(y_max + 0.5))
    # Draw the box on the image
    cv2.rectangle(
        img=img, pt1=upper_left_point, pt2=bottom_right_point, color=color, thickness=1
    )


def draw_boxes(img, boxes, colors):
    """Draws boxes on the original image instead of a copy.

    Args:
        img: Original image.
        boxes: A list of (x_min, y_min, x_max, y_max) boxes.
        colors: A list of BGR colors to cycle through for the boxes.
    """
    # Draw boxes one by one
    for box, color in zip(boxes, colors):
        draw_box(img, box, color)


def draw_polygon(img, polygon, color):
    """Draws a polygon on the original image instead of a copy.

    Args:
        img: Original image.
        polygon: [x1, y1, x2, y2, ...].
        color: (b, g, r).
    """
    # Arrange points in polygon
    polygon = np.array(polygon) + 0.5
    polygon = np.array(polygon, dtype=np.int32).reshape(-1, 1, 2)
    # Draw the polygon on the image
    cv2.polylines(img=img, pts=[polygon], isClosed=True, color=color, thickness=1)


def draw_polygons(img, polygons, colors):
    """Draws polygons on the original image instead of a copy.

    Args:
        img: Original image.
        polygons: A list of [x1, y1, x2, y2, ...] polygons.
        colors: A list of BGR colors to cycle through for the boxes.
    """
    # Draw polygons one by one
    for polygon, color in zip(polygons, colors):
        draw_polygon(img, polygon, color)


def draw_keypoints(img, kps, kp_threshold, kp_color, index_flag=False, edges=None):
    """Draws keypoints (with edges if exists) on the original image instead of a
    copy.

    Args:
        img: Original image.
        kps: A list of [x, y, confidence] keypoints.
        kp_threshold: The threshold for keypoint localization.
        kp_color: The (b, g, r) color for keypoint.
        index_flag: Used to indicate whether rendering the index of keypoint as
            text string in the image.
        edges: A list of edge which comprises the indexes of two keypoints,
        e.g., (2, 5).
    """
    for i, kp in enumerate(kps):
        if kp[2] >= kp_threshold:
            # Draw the keypoint
            cv2.circle(
                img=img,
                center=(int(kp[0] + 0.5), int(kp[1] + 0.5)),
                radius=3,
                color=kp_color,
                thickness=-1,
                lineType=cv2.FILLED,
            )
            if index_flag:
                cv2.putText(
                    img=img,
                    text=f"{i}",
                    org=(int(kp[0] + 0.5) - 5, int(kp[1] + 0.5) - 5),
                    fontFace=cv2.FONT_HERSHEY_SIMPLEX,
                    fontScale=0.5,
                    color=kp_color,
                    thickness=1,
                )
    if edges:
        for i, e in enumerate(edges):
            if min(kps[e[0]][2], kps[e[1]][2]) >= kp_threshold:
                # Get different colors for the edges
                rgb = 255 * matplotlib.colors.hsv_to_rgb([i / len(edges), 1.0, 1.0])
                bgr = (int(rgb[2]), int(rgb[1]), int(rgb[0]))
                # Join the keypoint pairs to draw the skeleton structure
                cv2.line(
                    img=img,
                    pt1=(int(kps[e[0]][0] + 0.5), int(kps[e[0]][1] + 0.5)),
                    pt2=(int(kps[e[1]][0] + 0.5), int(kps[e[1]][1] + 0.5)),
                    color=bgr,
                    thickness=2,
                    lineType=cv2.LINE_AA,
                )
