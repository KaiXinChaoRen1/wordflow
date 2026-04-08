"""CLI entrypoint for Wordflow."""

from .app import WordflowApp


def main() -> None:
    """Run the Textual app."""
    WordflowApp().run()


if __name__ == "__main__":
    main()
