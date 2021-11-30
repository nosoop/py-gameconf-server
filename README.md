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
    - You may also pass in `--config ${PATH}` to specify an alternate path for the config.
4. On your SourceMod installation, modify `configs/core.cfg` and point `AutoUpdateURL` to your
server.
    - **Important:**  Only use update servers you trust!

### Directory layout
The service searches the working directory for first-party game configs in "major.minor" format
subdirectories.  Add the configs into directories such as `1.9/`, `1.10/`.

The service also checks for matches in the `thirdparty/` directory, for game configs
that aren't tied to a specific SourceMod version.

Any game config files that are present on the server but missing on the client are ignored.
The official servers differ in this way, as they *do* send missing files.

## License
`gameconf-server` is provided under the MIT License.
