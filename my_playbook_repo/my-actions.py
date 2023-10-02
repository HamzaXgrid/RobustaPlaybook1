from robusta.api import *
import os

@action
def list_files_on_persistent_volume(event: PodEvent):
    # Get the pod object from the event
    pod = event.get_pod()

    # Specify the path to the Persistent Volume
    persistent_volume_path = "/mnt/data"

    try:
        # List all files in the specified path
        files = os.listdir(persistent_volume_path)
    except Exception as e:
        # Handle any exceptions if the directory doesn't exist or can't be accessed
        event.add_enrichment([
            TextBlock(f"Error: {str(e)}")
        ])
        return

    # Prepare a message with the list of files
    file_list_message = f"Files in the Persistent Volume ({persistent_volume_path}):\n"
    file_list_message += "\n".join(files)

    # Create a text block with the file list
    file_list_block = TextBlock(file_list_message)

    # Add the file list as an enrichment
    event.add_enrichment([
        MarkdownBlock(file_list_block)
    ])
