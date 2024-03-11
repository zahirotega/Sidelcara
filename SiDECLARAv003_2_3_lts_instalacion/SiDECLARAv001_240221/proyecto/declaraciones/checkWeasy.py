import subprocess
import sys
weasyVersion = str(sys.argv[1])
try:
    import weasyprint

    if weasyprint.__version__ != weasyVersion:
        subprocess.run(["pip", "uninstall", "--yes", "weasyprint"])
        subprocess.run(["pip", "install", "weasyprint=="+weasyVersion])
    else:
        print('La versión actual es correcta '+weasyVersion)
except:
    subprocess.run(["pip","install","weasyprint=="+weasyVersion])
