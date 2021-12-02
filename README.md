# gameconf-server
A library that processes and responds to game config requests from [SourceMod][] installations.

I've had this idea on the backburner for years.
Not sure what to do now that I've actually done it.

[SourceMod]: https://www.sourcemod.net/

## Setup
Run `pip install git+https://github.com/nosoop/py-gameconf-server#egg=gameconf-server`
(preferably in a venv).

## Standalone server
The package provides a runnable server implementation (based on the built-in `http.server`) for
testing or just serving your own files.  Run `python -m gameconf_server.http_server` to use it.

You will need to provide a configuration file; see `config.example.ini` for details.  You may
also pass in `--config ${PATH}` to specify an alternate path for the config.

On your SourceMod installation, modify `configs/core.cfg` and point `AutoUpdateURL` to your
server.

The service searches the working directory for first-party game configs in "major.minor" format
subdirectories.  Add the configs into directories such as `1.9/`, `1.10/`.

The service also checks for matches in the `thirdparty/` directory, for game configs
that aren't tied to a specific SourceMod version.

Any game config files that are present on the server but missing on the client are ignored.
The official servers differ in this way, as they *do* send missing files.

## License
`gameconf-server` is provided under the MIT License.
