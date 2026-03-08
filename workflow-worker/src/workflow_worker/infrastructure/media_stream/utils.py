from workflow_worker.domain.entities.frame import BatchFrame


def gather_batch_frames_from_generator(msg_gen, process_step, batch_size):
    frames = []
    count = -1
    for stream_msg in msg_gen:
        if stream_msg is None:
            break
        if stream_msg.image is None:
            continue

        frame = stream_msg.image
        count += 1
        if count % process_step != 0:
            continue
        frames.append(frame)
        if len(frames) == batch_size:
            yield BatchFrame(frames=frames, batch_size=len(frames))
            frames = []
    # the last batch
    if len(frames) > 0:
        yield BatchFrame(frames=frames, batch_size=len(frames))
