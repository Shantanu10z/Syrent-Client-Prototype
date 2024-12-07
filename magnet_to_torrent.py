import subprocess
import sys
import os

def convert_magnet_to_torrent(magnet_link, output_dir):
    """
    Converts a magnet link to a .torrent file and saves it in the specified output directory.
    """
    # Define the output file name
    output_file = os.path.join(output_dir, "output.torrent")

    # Full path to m2t command (using the .cmd extension for Windows)
    m2t_path = "C:\\Users\\Shantanu Anand\\AppData\\Roaming\\npm\\m2t.cmd"

    # Formulate the command as a single string with proper quoting for Windows
    command = f'"{m2t_path}" -o "{output_file}" "{magnet_link}"'

    print(f"Running command: {command}")  # Debugging output

    # Run the command and capture the output
    try:
        # Using shell=True to pass the entire command as a single string
        result = subprocess.run(command, capture_output=True, text=True, shell=True)
        
        # Check if the command was successful
        if result.returncode == 0:
            print(f"Success: Torrent file saved at {output_file}")
            if os.path.exists(output_file):
                print("File successfully created.")
            else:
                print("Error: File was not created despite success message.")
            print(result.stdout)  # Optional: Print any output from the command for debugging
        else:
            print("Command failed.")
            print(f"Error: {result.stderr}")
    
    except subprocess.CalledProcessError as e:
        print(f"Subprocess error: {e.stderr}")
    except FileNotFoundError:
        print("Error: The specified m2t path does not exist. Please check the path.")

if __name__ == "__main__":
    # Check if the user provided the magnet link and output directory as command-line arguments
    if len(sys.argv) < 3:
        print("Usage: python magnet_to_torrent.py <magnet_link> <output_directory>")
        sys.exit(1)

    # Get the magnet link and output directory from command-line arguments
    magnet_link = sys.argv[1]
    output_dir = sys.argv[2]

    # Ensure output directory exists
    if not os.path.isdir(output_dir):
        print("Error: The specified output directory does not exist.")
        sys.exit(1)

    # Convert the magnet link to a torrent file
    convert_magnet_to_torrent(magnet_link, output_dir)
