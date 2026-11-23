"""Run FarmTrack:  python main.py"""
from farmtrack.app import FarmTrackApp
from farmtrack.exceptions import StorageError
from farmtrack.storage import JsonStorage


def main() -> None:
    storage = JsonStorage("farmtrack_data.json")
    try:
        app = FarmTrackApp(storage)
    except StorageError as error:
        # Do NOT continue: saving would overwrite the (possibly recoverable) file.
        print(f"Error: {error}")
        print("Fix or rename the data file, then start again.")
        return
    app.run()


if __name__ == "__main__":
    main()
