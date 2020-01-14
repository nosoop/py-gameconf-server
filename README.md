# gameconf-server
An HTTP service that processes and responds to game config requests from SourceMod
installations.

## Configuration

### Dependencies
- [vdf](https://github.com/ValvePython/vdf)

### Initial setup
Refer to `config.example.ini` for configuration options; copy or rename to `config.ini` and
modify as desired.

Run the script to start the server.  You may want to daemonize it in some way; that's left for
you to do.

### Directory layout
The service searches the working directory for first-party game configs in "major.minor" format
subdirectories.  Add the configs into directories such as `1.9/`, `1.10/`.

The service also checks for matches in the `thirdparty/` directory, for game configs
that aren't tied to a specific SourceMod version.

## License
`gameconf-server` is provided under the AGPLv3 license.  Basically, this means that:

- If you host a copy of the server with modified code, you must publish the code and state the
changes you've made.
    - This allows everyone to benefit from any improvements other people make to the software.
    - You'll also need to make sure any libraries you use are inbound compatible.
- Any additional software that runs alongside the server (e.g., a separate service that updates
the game config files) are not bound by the AGPLv3.
