# serve.py
# Thin wrapper — just calls server.py's main().
# Kept so both "python serve.py" and "python server.py" work.

from server import main

if __name__ == "__main__":
    main()
