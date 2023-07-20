from . import models

def post_init_hook(cr, registry):
    # Look for .gitmodules file
    gitmodules_file = os.path.join(os.getcwd(), '.gitmodules')
    if os.path.exists(gitmodules_file):
        # Read .gitmodules file
        with open(gitmodules_file) as f:
            content = f.read()
            # Extract installed directory
            installed_directory = re.search('[submodule "(.*)"]', content).group(1)
            print(installed_directory)
