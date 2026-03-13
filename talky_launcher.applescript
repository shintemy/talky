on run
	set scriptPath to "/path/to/start_talky.command"
	set cmd to "zsh " & quoted form of scriptPath
	
	-- Check whether Talky is already running (by main.py process)
	try
		set runningCount to (do shell script "pgrep -f " & quoted form of "python.*main.py" & " | wc -l | tr -d ' '") as integer
	on error
		set runningCount to 0
	end try
	
	if runningCount > 0 then
		display notification "Talky is already running." with title "Talky Launcher"
		return
	end if
	
	tell application "Terminal"
		if not running then launch
		
		if (count of windows) = 0 then
			do script cmd
		else
			do script cmd in front window
		end if
		
		activate
	end tell
end run
