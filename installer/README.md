## Installer

The installer sets up napari and napari-cellposesam, with the PyTorch build for your computer's graphics card (NVIDIA, AMD on Linux, or Apple silicon).
If your computer has none of these, it installs the PyTorch build that runs on the processor (CPU).
You do not need Python or conda. You need an internet connection while it runs.

### Install on Windows

Download `napari-cellposesam-setup.exe` from the [releases page](https://github.com/DBI-INFRA/napari-cellposesam/releases) and run it.
It is under **Assets** in the newest release.
The setup is not code-signed, so Windows may show "Windows protected your PC".
If it does, click **More info**, then **Run anyway**.

While the setup installs, a black window shows the download progress.
Leave it open. It closes by itself when the installation is done.

You can also install without the setup. Open PowerShell (search for it in the Start menu) and run:

```
powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/DBI-INFRA/napari-cellposesam/main/installer/install.ps1 | iex"
```

### Install on macOS or Linux

Open a terminal and run the command below. On macOS, the Terminal app is in Applications > Utilities.

```
curl -LsSf https://raw.githubusercontent.com/DBI-INFRA/napari-cellposesam/main/installer/install.sh | sh
```

If the terminal says `curl` is not found, as on a fresh Ubuntu, run this instead:

```
wget -qO- https://raw.githubusercontent.com/DBI-INFRA/napari-cellposesam/main/installer/install.sh | sh
```

Recent versions of PyTorch do not support Macs with an Intel processor, so the installation may fail on those Macs.

The installer offers to download the Cellpose-SAM model (about 1.2 GB) as part of the installation: tick the box in the Windows setup, or answer the question in the terminal.

### Where it goes

Everything goes into one folder: `%LOCALAPPDATA%\napari-cellposesam` on Windows, and `~/.local/share/napari-cellposesam` on macOS and Linux.
With PyTorch, this folder can take several GB of disk space.

### Start napari

Start napari with the "napari-cellposesam" shortcut.
It is on your desktop, and also in the Start menu on Windows, in the Applications folder of your home folder on macOS, and in the app menu on Linux.
napari opens with napari-cellposesam ready to use. The first start can be slow; later starts are quicker.

### Update

To update, run the install command again, or download and run the newest setup.

### Uninstall

If you installed with the setup, uninstall "napari-cellposesam" in Windows Settings > Apps > Installed apps (on Windows 10, Apps & features).
Otherwise, run the command for your system.

On Windows, in PowerShell:

```
powershell -ExecutionPolicy ByPass -c "& ([scriptblock]::Create((irm https://raw.githubusercontent.com/DBI-INFRA/napari-cellposesam/main/installer/install.ps1))) -Uninstall"
```

On macOS or Linux, in a terminal:

```
curl -LsSf https://raw.githubusercontent.com/DBI-INFRA/napari-cellposesam/main/installer/install.sh | sh -s -- --uninstall
```

or, without `curl`:

```
wget -qO- https://raw.githubusercontent.com/DBI-INFRA/napari-cellposesam/main/installer/install.sh | sh -s -- --uninstall
```

### If something goes wrong

If the installation stops with an error, check your internet connection and run the installer again.
On Windows, the end of `install.log` in the install folder says what went wrong.
On macOS and Linux, the error is in the last lines in the terminal.
If it still fails, or napari does not start, report it on the [issues page](https://github.com/DBI-INFRA/napari-cellposesam/issues) and include those lines.

### Advanced options

The top of each install script lists environment variables that change the install folder, the plugin version and the PyTorch build.

If you already have a Python environment with napari-cellposesam, you can make the same shortcut for it:

```
pip install napari-launcher
napari-launcher shortcut add -w napari-cellposesam "cellpose" --name "napari-cellposesam"
```
