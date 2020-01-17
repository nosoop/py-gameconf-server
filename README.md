# gameconf-server
An HTTP service that processes and responds to game config requests from [SourceMod][]
installations.

I've had this idea on the backburner for years.
Not sure what to do now that I've actually done it.

[SourceMod]: https://www.sourcemod.net/

## Configuration

### Dependencies
- [Poetry](https://github.com/python-poetry/poetry)

### Initial setup
1. Clone the repository, then `poetry install`.
2. Refer to `config.example.ini` for configuration options; copy or rename to `config.ini` and
modify as desired.
3. Use `poetry run server` to start the server.  You may want to daemonize it in some way;
that's left for you to do.
4. On your SourceMod installation, modify `configs/core.cfg` and point `AutoUpdateURL` to your
server.

**Important:**  Only use update servers you trust!

### Directory layout
The service searches the working directory for first-party game configs in "major.minor" format
subdirectories.  Add the configs into directories such as `1.9/`, `1.10/`.

The service also checks for matches in the `thirdparty/` directory, for game configs
that aren't tied to a specific SourceMod version.

## License
`gameconf-server` is provided under the AGPLv3 license.  Basically, this means that:

- If you publicly host a copy of the server with modified code, you must publish the code and
state the changes you've made.
    - This allows everyone to benefit from any improvements other people make to the software.
    - You'll also need to make sure any libraries you use are inbound compatible.
- If you run a modified copy that is bound to `localhost` or is otherwise only accessible within
a closed network (such as for a group of servers), only those consumers are required to have
access to the source.  It is your responsibility to ensure it's not internet-facing.
- Any additional software that runs alongside the server (e.g., a separate service that updates
the game config files) is not bound by the AGPLv3.
