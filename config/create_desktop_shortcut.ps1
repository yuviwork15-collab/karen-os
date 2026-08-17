$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut('C:\Users\Admin\Desktop\Karen - Premium.lnk')
$Shortcut.TargetPath = 'C:\Users\Admin\Desktop\Brahma-Echo-main\.venv\Scripts\pythonw.exe'
$Shortcut.Arguments = '"C:\Users\Admin\Desktop\Brahma-Echo-main\main.py"'
$Shortcut.WorkingDirectory = 'C:\Users\Admin\Desktop\Brahma-Echo-main'
$Shortcut.WindowStyle = 7
$Shortcut.Description = 'Launch Karen - Premium'
if ('C:\Users\Admin\Desktop\Brahma-Echo-main\assets\Brahma_Lite_Logo.ico') { $Shortcut.IconLocation = 'C:\Users\Admin\Desktop\Brahma-Echo-main\assets\Brahma_Lite_Logo.ico,0' }
$Shortcut.Save()