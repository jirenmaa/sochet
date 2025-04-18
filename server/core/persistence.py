from utils.helpers import save_json


def save_data(path: str, data: any):
    """Saves data to DB."""
    save_json(path, data)
