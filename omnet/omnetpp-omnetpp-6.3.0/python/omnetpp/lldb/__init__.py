import os
import lldb

# Check for a reliable indicator of a container (like /.dockerenv)
is_docker = os.path.exists("/.dockerenv") or (os.environ.get("container", "").strip() != "")

# Check for a reliable indicator of WSL (like the presence of the /proc/version_signature file)
# The output of this file often contains "Microsoft"
is_wsl = "Microsoft" in open('/proc/version_signature', 'r', encoding='utf-8').read() if os.path.exists('/proc/version_signature') else False

if is_docker or is_wsl:
    # This prevents the "Operation not permitted" error by telling LLDB not to try
    # to disable ASLR, which it lacks the permissions to do in a restricted environment.
    lldb.debugger.HandleCommand('settings set target.disable-aslr false')
    print("ASLR setting cannot be adjusted automatically on WSL/Container environment.")
else:
    # On a native Linux/macOS host, LLDB's default behavior to disable ASLR typically works.
    pass