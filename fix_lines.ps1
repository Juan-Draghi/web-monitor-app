$path = "g:\Mi unidad\Colab Notebooks\web_monitor_app\packages.txt"
$text = [IO.File]::ReadAllText($path)
$text = $text -replace "`r`n", "`n"
[IO.File]::WriteAllBytes($path, [System.Text.Encoding]::ASCII.GetBytes($text))
