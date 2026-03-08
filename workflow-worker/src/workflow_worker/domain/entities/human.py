# pylint: disable=no-name-in-module,no-self-argument


from pydantic import BaseModel


class Face(BaseModel):
    """Face is designed to represent a face in one frame.

    Attributes:
        face_bbox: The (x_min, y_min, x_max, y_max) face bounding
            box on the origin image.
        face_id: The face id representing the face.
        score: The confidence from ai service.
        face_feature: The face feature embedding in low dimension,
            which from face detection service.
    """

    face_bbox: list[int]

    face_id: str | None = ""
    score: float | None = 0.0
    face_feature: list[float | None] | None = None

    def __hash__(self):
        return hash(str(sorted(self.face_bbox)) + (self.face_id or "") + str(self.score))

    def __eq__(self, other):
        return self.__hash__() == other.__hash__()


class Body(BaseModel):
    """Body is designed to represent a human body in frame.

    Attributes:
        body_bbox: The (x_min, y_min, x_max, y_max) human body
            bounding box.
        confidence: The body detection confidence from body detection
            service.
    """

    body_bbox: list[int]
    confidence: float

    def __hash__(self):
        return hash(str(sorted(self.body_bbox)) + str(self.confidence))

    def __eq__(self, other):
        return self.__hash__() == other.__hash__()


class Human(BaseModel):
    """Human is designed to represent human with face and body in frame.

    Attributes:
        tracking_id: The participant id in tracking service.
        participant_id: The identity of the human.
        body_info: The body info of human.
        face_info: The face info of human.
        tolerance: The maximum number of frames allowed for tracking failure.
        ttl: Time to live.
    """

    face_info: Face | None = None
    body_info: Body | None = None
    ttl: int | None = None

    tracking_id: str | None = ""
    participant_id: str | None = ""
    tolerance: int | None = 2

    def update(self, human_info):
        """Updates self with input human info.

        Args:
            human_info (HumanInfo): The human info at the current moment.
        """

        if human_info.face_info is not None:
            self.face_info = human_info.face_info

        if human_info.body_info is not None:
            self.body_info = human_info.body_info

        self.ttl = self.tolerance
