import requests
from io import BytesIO
import puremagic


def find_puremagic_ext(path):
    """
    Validate the file extension returned by puremagic.
    Try to go through and see if either jpeg, png, or gif.
    """
    with requests.Session() as session:
        b = BytesIO(session.get(path).content)
        stream = puremagic.magic_stream(b)

    for stream in stream:
        if stream.extension in [".jpeg", ".png", ".gif"]:
            return stream.extension.replace(".", "")
    return None
