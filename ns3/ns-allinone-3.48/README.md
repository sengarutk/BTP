This is **_ns-3-allinone_**, a repository with some scripts that bundle
ns-3's mainline source code with compatible
[App Store modules](https://apps.nsnam.org).

The mainline ns-3 release or development tree (ns-3-dev) only contains
the ns-3 project's maintained
modules (libraries) as found in the `src/` directory.  The `contrib/`
directory is empty in the project mainline, allowing users to later
download or clone extension modules to it.

In contrast, the ns-3 source code in this release contains several
additional contrib modules known to work with the release.  In
all other respects, this release should be identical with the main
tree release with the same number.

## Usage

If you have downloaded this as a source archive of a release, simply
recurse into the ns-3 directory and configure and build ns-3 as usual.
The build process will include all modules found in the contrib directory
that are compatible with your system (as detected by the `ns3` build
script).  If you are not interested in some of the contributed modules,
and want to shorten the compilation time, feel free to delete any such
subdirectories from your `contrib` directory.
 
If you have cloned ns-3-allinone.git, you can checkout the manifest
that corresponds to a particular release by checking out a tagged
branch such as follows.

By default, the `download.py` script will clone ns-3-dev (the development
version) with the master branch:

```shell
./download.py
```

After the above command succeeds, an `ns-3-dev` directory will be
present containing the development version, and within that directory's
contrib directory, several extension modules will be downloaded.
`download.py` reports on the extra modules that have been downloaded.

Note that using ns-3-dev may lead to compilation errors if the contrib
modules listed in `MANIFEST.md` have not been upgraded to ns-3-dev
compatibility, but any such modules could either be fixed locally or
else deleted if not of interest.

To download the latest release instead:

```shell
./download.py --latest
```

This will find and checkout the most recent release tag (e.g., ns-3.47),
creating a directory named after that release.

To download a specific release:

```shell
./download.py -r ns-3.45
```

This will checkout the specified release tag and create a directory
with that name.  

ns-3.45 is the earliest such release that is supported; see
[History](#history) below for ns-3-allinone prior to ns-3.45.

## Documentation

The manifest of contributed modules can be found in [MANIFEST.md](MANIFEST.md).
This release does not package documentation of the contributed modules; please
visit the App Store page or the module's repository itself for such documentation.
 
## Scope and Limitations

The ns-3 mainline undergoes thorough CI testing of the build on many
systems and compiler versions, as well as documentation and code style
checks.  Contributed modules are not subjected to the same level of testing
or adherence to style or other conventions.  This distribution errs on the
side of inclusion of many modules so that users may learn about them,
with the downside that users may encounter compilation problems on some
systems.  The easiest fix is to delete any contrib modules that are
causing problems, unless of course you want to use those modules, in which
case you will need to fix that code by hand.

If users find a compatibility issue with a contributed module, please
file an issue on the upstream module's issue tracker, not on ns-3-allinone.

## Proposing New Modules

To recommend a new module for future inclusion in ns-allinone, please post
a pull request to https://gitlab.com/nsnam/ns-3-allinone repository to
add it to the file `MANIFEST.md`.

To test it for inclusion, you can follow these steps:

1. Run `./download.py` to clone ns-3-dev and all modules listed in MANIFEST.md.
   Alternatively, use `./download.py -r ns-3.XX` to test against a specific
   release that is being prepared for allinone release.

2. cd into ns-3-dev (or ns-3.XX), configure ns-3 with examples and tests,
   and build and run test.py.

If your module depends on additional third-party libraries (such as Boost),
your module must still compile cleanly on a system that does not have these
dependencies.  A good way to check this is to perform the above test on a
Docker container that has the minimal ns-3 requirements (CMake, Python3 and
a c++ compiler).

## History

Prior to the ns-3.45 release, ns-3-allinone was a bundle that included
the [bake packaging tool](https://gitlab.com/nsnam/bake.git), the
[NetAnim](https://gitlab.com/nsnam/netanim.git) network animator, and
ns-3.  Starting with ns-3.45, ns-3-allinone was changed to focus instead
on ns-3 and compatible contributed App Store modules.

ns-3-allinone used to have a `build.py` script, but building is now
only coordinated by the `ns3` script.
