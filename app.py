# Keep the command-line entry point small; application setup lives in backend.
from backend import create_app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
