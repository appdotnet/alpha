
from pau.constants import CORE_OEMBED


def _check_core_oembed(oembed_type):
    def inner(annotation_dict):
        annotation_type = annotation_dict.get('type')
        if annotation_type == CORE_OEMBED:
            value = annotation_dict.get('value')
            if value:
                value_type = value.get('type')
                version = value.get('version')
                width = value.get('width')
                height = value.get('height')
                thumbnail_width = value.get('thumbnail_width')
                thumbnail_height = value.get('thumbnail_height')
                thumbnail_url = value.get('thumbnail_url')
                return all([version == '1.0', value_type == oembed_type, width, height, thumbnail_width, thumbnail_height,
                            thumbnail_url])
    return inner


is_photo_annotation = _check_core_oembed('photo')
is_video_annotation = lambda annotation: _check_core_oembed('video')(annotation) or _check_core_oembed('html5video')(annotation)


def get_photo_annotations(annotations):
    return filter(is_photo_annotation, annotations)


def get_video_annotations(annotations):
    return filter(is_video_annotation, annotations)


def get_attachment_annotations(annotations):
    return filter(lambda a_dict: a_dict.get('type') == 'net.app.core.attachments', annotations)


def get_place_annotation(annotations):
    place = None
    for a in annotations:
        annotation_type = a.get('type')
        if annotation_type in ('net.app.core.checkin', 'net.app.ohai.location'):
            value = a.get('value')
            if value:
                if value.get('name'):
                    place = a
    return place
