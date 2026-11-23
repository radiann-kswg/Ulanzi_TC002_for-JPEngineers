@echo off
setlocal
pushd "%~dp0" || exit /b 1
if exist "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" -c "import tkinter" >nul 2>nul && (
        start "" "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" -m studio
        goto done
    )
)
where pyw.exe >nul 2>nul
if not errorlevel 1 (
    pyw -3.12 -c "import tkinter" && (start "" pyw -3.12 -m studio & goto done)
)
where pythonw.exe >nul 2>nul
if not errorlevel 1 (
    pythonw -c "import sys,tkinter;sys.exit(sys.version_info[:2] != (3,12))" && (start "" pythonw -m studio & goto done)
)
echo TC002 Studio requires Python 3.12 with Tcl/Tk.
echo Install the Windows desktop edition from python.org, then try again.
pause
popd
exit /b 1
:done
popd
