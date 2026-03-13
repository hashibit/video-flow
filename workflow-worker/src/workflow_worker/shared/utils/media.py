import json
import os
import re
from fractions import Fraction
from typing import Any

import cv2  # pyright: ignore[reportMissingImports]
import ffmpeg  # pyright: ignore[reportMissingImports]
import numpy as np

from workflow_worker.domain.entities.frame import BatchFrame, Frame
from workflow_worker.shared.utils.frame import encode_image


def extract_audio(
        input_file: str,
        output_file: str,
        audio_format: str,
        rate: int | str = 16000,
        bits: int = 16,
        channel: int = 2,
        quiet: bool = True,
        overwrite: bool = True,
) -> None:
    """Extracts and saves audio from media file.

    Args:
        input_file (str): The path of input media file.
        output_file (str): The path of output audio file.
        audio_format (str): The audio format, support pcm and m4a.
        rate (int | str, optional): Audio bitrate, eg. 16000(int),
            `16k`(str). Defaults to 16000.
        bits (int, optional): The bits of audio encode, eg. 16. Defaults to 16.
        channel (int, optional): Channel of audio, only can be set to 1 or 2.
            The value `1` means mono and `2` means stereo. Defaults to 2.
        quiet (bool, optional): Not print logs. Defaults to True.
        overwrite (bool, optional): Overwrites the same name output. Defaults to
            True.

    Raises:
        ffmpeg.Error: FFmpeg errors.
    """

    # mapping ffmpeg audio format
    if audio_format == "pcm":
        result_format = f"s{bits}le"
    elif audio_format == "m4a":
        result_format = "adts"
    else:
        raise ValueError("audio format only can be `pcm` or `m4a`")

    # set ffmpeg input and output format
    stream = ffmpeg.input(input_file).audio
    # ar means audio rate, ac means audio channel
    stream = ffmpeg.output(
        stream, output_file, format=result_format, ar=rate, ac=channel
    )
    stream = stream.global_args("-nostdin")
    try:
        # run ffmpeg
        # the FFmpeg param `quiet` is always set to True, so that the var `logs`
        # can accept the logs or err from the FFmpeg. It is different from this
        # function"s param `quiet` which will use to control this function"s log
        # not only FFmpeg.
        _, logs = ffmpeg.run(
            stream, quiet=True, overwrite_output=overwrite, capture_stderr=True
        )

    except ffmpeg.Error as e:
        # If quiet is True, the error info will output to the Error.stderr
        if quiet:
            print(e.stderr.decode("utf-8"))
        raise e

    # if quiet is False, print the info from var logs
    if not quiet:
        print(logs.decode("utf-8"))


def extract_frames(
        input_file: str,
        output_dir: str,
        output_format: str = "%05d.jpg",
        fps: str | int = 1,
        qscale: int = 2,
        quiet: bool = True,
        overwrite: bool = True,
) -> None:
    """Extracts and saves frames from media file.

    Args:
        input_file (str): The path of input media file.
        output_dir (str): The dir of output frames.
        output_format (str): The output format. It shoud figure out the control
            format and extension. Eg. `%05d.png`.
        fps (str | int): Sample fps. Eg. 1(int), `1/2`(str)
        qscale (int, optional): Scale quality. Defaults to 2.
        quiet (bool, optional): Not print log. Defaults to False.
        overwrite (bool, optional): Overwrites the same name output. Defaults to
            True.

    Raises:
        ffmpeg.Error: FFmpeg error.
    """

    if not os.path.exists(output_dir):
        os.mkdir(output_dir)

    # complete output path
    output = os.path.join(output_dir, output_format)

    # params for output frame quality
    kwargs = {"qscale:v": qscale, "vf": f"fps=fps={fps},showinfo"}

    # set ffmpeg input and output format
    stream = ffmpeg.input(input_file)

    # format: "image2" means convert raw video frame to image.
    # frame_pts: true means frame name will same with pts number.
    # vsync: 0 means each frame is passed with its timestamp from the demuxer
    # to the muxer.
    stream = ffmpeg.output(
        stream, output, format="image2", vsync=0, frame_pts=True, **kwargs
    )
    stream = stream.global_args("-nostdin")
    try:
        # run FFmpeg
        # the explain of ffmpeg param `quiet` can be found in the function
        # `extract_audio` at the head of this file.
        _, logs = ffmpeg.run(
            stream, quiet=True, overwrite_output=overwrite, capture_stderr=True
        )

    except ffmpeg.Error as e:
        # if quiet is True, the error info will output to the Error.stderr
        if quiet:
            print(e.stderr.decode("utf-8"))
        raise e

    # if quiet is False, print the info from var logs
    if not quiet:
        print(logs.decode("utf-8"))

    # extract paired (frame_num, pts_time) from logs
    # PTS: Presentation Timestamp
    frames_info = re.findall(
        r"([0-9]*) pts_time:([0-9]*\.?[0-9]*)", logs.decode("utf-8")
    )

    # convert pairs to dict object
    frames_record: dict[str, list[Any]] = {"frames": []}
    for frame_num, pts_time in frames_info:
        frames_record["frames"].append(
            {
                "frame_name": output_format % int(frame_num),
                "pts_time": int(float(pts_time) * 1000),
            }
        )

    # write down to json file
    with open(os.path.join(output_dir, "frames_info.json"), "w") as f:
        json.dump(frames_record, f)


def extract_frames_and_audio(
        media_file: str,
        output_dir: str,
        frame_output_format: str = "%5d.png",
        frame_fps: int | str = 1,
        frame_qscale: int = 2,
        audio_format: str = "pcm",
        audio_rate: int | str = 16000,
        audio_bits: int = 16,
        audio_channel: int = 2,
        quiet: bool = True,
        overwrite: bool = True,
) -> None:
    """Extracts audio and frames from media and save as files.

    Args:
        media_file (str): Path of media file.
        output_dir (str): The output dir.
        frame_output_format (str, optional): Outputs frame control format.
            Defaults to "%5d.png".
        frame_fps (int | str, optional): Sample frame fps. Defaults to 1.
        frame_qscale (int, optional): Video qscale. Defaults to 2.
        audio_format (str, optional): Audio format, can be set to "pcm" or
            "m4a". Defaults to "pcm".
        audio_rate (int | str, optional): Audio rate. Defaults to 16000.
        audio_bits (int, optional): Audio encode bits. Defaults to 16.
        audio_channel (int, optional): Audio channel. Defaults to 2.
        quiet (bool, optional): Not print the logs. Defaults to True.
        overwrite (bool, optional): Overwrites the same name file. Defaults to
            True.
    """

    if not os.path.exists(output_dir):
        os.mkdir(output_dir)

    # get the filename, audio files will use this filename
    _, tempfilename = os.path.split(media_file)
    filename, _ = os.path.splitext(tempfilename)

    # extract audio from media file
    pcm_path = os.path.join(output_dir, f"{filename}.{audio_format}")
    extract_audio(
        input_file=media_file,
        output_file=pcm_path,
        audio_format=audio_format,
        rate=audio_rate,
        bits=audio_bits,
        channel=audio_channel,
        quiet=quiet,
        overwrite=overwrite,
    )

    # extract frames from media file
    frame_output_dir = os.path.join(output_dir, "frames")
    extract_frames(
        input_file=media_file,
        output_dir=frame_output_dir,
        output_format=frame_output_format,
        fps=frame_fps,
        qscale=frame_qscale,
        quiet=quiet,
        overwrite=overwrite,
    )


def extract_media_info(media_file, fps: int = 1, frame_qscale: int = 2) -> dict[str, Any]:
    kwargs = {"qscale:v": frame_qscale, "vf": f"fps=fps={fps},showinfo"}
    stream = ffmpeg.input(media_file)
    stream = stream.output("pipe:", format="rawvideo", pix_fmt="rgb24", **kwargs)
    stream = stream.global_args("-nostdin")
    stream = stream.run_async(pipe_stdout=True, pipe_stderr=True)
    _, info = stream.communicate()
    # extract paired (frame_num, pts_time) from logs
    # PTS: Presentation Timestamp
    frames_info = re.findall(
        r"([0-9]*) pts_time:([0-9]*\.?[0-9]*)", info.decode("utf-8")
    )

    # convert pairs to dict object
    frames_record: dict[str, list[Any]] = {"frame_pts": []}
    for i, (_, pts_time) in enumerate(frames_info):
        frames_record["frame_pts"].append(
            {"index": i, "pts_time": int(float(pts_time) * 1000)}
        )

    # extract video info
    probe = ffmpeg.probe(media_file)
    video_info = next(s for s in probe["streams"] if s["codec_type"] == "video")
    frames_record["meta"] = video_info
    return frames_record


def extract_video_metadata(media_file: str):
    """Extract the metadata of video stored as a file.

    Args:
        media_file (str): Input media path, both support local path and url.

    Returns:
        (dict): A dict of video metadata fields to their values.
    """
    media_information = ffmpeg.probe(media_file)
    # Grab the format name of the video
    format_name = media_information["format"]["format_name"]

    # Grab the storage size in bytes of the video
    size = media_information["format"]["size"]

    # Grab the media bit rate of the video
    video_bit_rate = media_information["format"].get("bit_rate", -1)

    # Used ot grab the resolution and fps of the video
    resolution, fps, duration, bit_rate = None, None, None, None
    width: int = 0
    height: int = 0
    # Grab video stream
    for stream in media_information["streams"]:
        if stream["codec_type"] == "video":
            video_stream = stream
            # Grab the resolution of the video
            width = video_stream["width"]
            height = video_stream["height"]
            resolution = f"{width}x{height}"

            # Grab the fps of the video
            fps = float(Fraction(video_stream["avg_frame_rate"]))
            duration = float(video_stream["duration"]) * 1000.0

            # Grab bit_rate of the video stream
            bit_rate = float(video_stream.get("bit_rate", video_bit_rate))
            if bit_rate <= 0:
                bit_rate = size / float(video_stream["duration"]) * 8
            break

    return {
        "width": int(width),
        "height": int(height),
        "resolution": resolution,
        "fps": fps,
        "format_name": format_name,
        "size": size,
        "duration": duration,
        "bitrate": bit_rate,
    }


def gather_batch_frames(
        media_file, width, height, fps=2, batch_size=1, ts=0.0, cut_count=None
):
    """Extract frames from media and return the frames in BatchFrame format.
    Using ffmpeg to extract batch_size pictures at one time.

    Args:
        media_file (_type_): the path of media file.
        width (_type_): the origin width of frame.
        height (_type_): the origin height of frame.
        fps (int, optional): extracted frame rate. Defaults to 2.
        batch_size (int, optional): the max size of frames at one time. Defaults to 1.
        ts (float, optional): the start timestamp. Defaults to 0.0.

    Yields:
        BatchFrame: the extracted frames.
    """
    kwargs = {"qscale:v": 2, "vf": f"fps=fps={fps},showinfo"}
    stream = ffmpeg.input(media_file)
    stream = stream.output("pipe:", format="rawvideo", pix_fmt="bgr24", **kwargs)
    stream = stream.global_args("-nostdin", "-loglevel", "quiet")
    stream = stream.run_async(pipe_stdout=True)

    frame_id = 0

    frames = BatchFrame(frames=[], batch_size=0)
    channel = 3
    while True:
        in_bytes = stream.stdout.read(width * height * channel)
        if not in_bytes:
            if frames.batch_size > 0:
                if cut_count:
                    frames.frames = frames.frames[:cut_count]
                    frames.batch_size = cut_count
                yield frames
            break
        in_frame = np.frombuffer(in_bytes, np.uint8).reshape([height, width, channel])
        # print(in_frames.shape)
        img_bytes = encode_image(in_frame)
        frame = Frame(
            frame_number=frame_id,
            url="",
            data=img_bytes,
            timestamp=ts,
        )
        frame_id += 1

        ts += 1.0 / fps * 1000
        frames.frames.append(frame)
        frames.batch_size += 1
        if frames.batch_size == batch_size:
            if cut_count:
                frames.frames = frames.frames[:cut_count]
                frames.batch_size = cut_count
            yield frames
            frames = BatchFrame(frames=[], batch_size=0)


def gather_batch_frames_opencv(
        media_file, width, height, fps=2, batch_size=1, ts=0.0, cut_count=None
):
    frames = BatchFrame(frames=[], batch_size=0)
    cap = cv2.VideoCapture(media_file)
    video_fps = round(cap.get(5))  # CV_CAP_PROP_FPS = 5
    frame_rate = int(1.0 / fps * video_fps)
    print("video fps is {}; frame rate is {}".format(video_fps, frame_rate))
    index = 0
    while True:
        ret, frame = cap.read()
        if ret:
            if index % frame_rate == 0:
                img_bytes = encode_image(frame)
                print("extracing ts:{} size:{}MB".format(ts, len(img_bytes) / 1024 / 1024))
                frame = Frame(
                    url="",
                    data=img_bytes,
                    timestamp=ts,
                )
                ts += 1.0 / fps * 1000
                frames.frames.append(frame)
                frames.batch_size += 1
                if frames.batch_size == batch_size:
                    if cut_count:
                        frames.frames = frames.frames[:cut_count]
                        frames.batch_size = cut_count
                    yield frames
                    frames = BatchFrame(frames=[], batch_size=0)
            index += 1
        else:
            if frames.batch_size > 0:
                if cut_count:
                    frames.frames = frames.frames[:cut_count]
                    frames.batch_size = cut_count
                yield frames
            break
