
from robusta.api import *
import os
@action
def list_files_on_persistent_volume(event: PersistentVolumeEvent):
    # Get the pod object from the event
    pv = event.get_persistentvolume()

    # Specify the path to the Persistent Volume
    persistent_volume_path = "/mnt/data" 

    try:
        # List all files in the specified path
        files = os.listdir(persistent_volume_path)
    except Exception as e:
        # Handle any exceptions if the directory doesn't exist or can't be accessed
        error_message = f"Error: {str(e)}"
        event.add_enrichment(MarkdownBlock("*Oh no!* An alert occurred on "))
        return

    # Prepare a message with the list of files
    file_list_message = f"Files in the Persistent Volume ({persistent_volume_path}):\n"
    file_list_message += "\n".join(files)

    # Create a MarkdownBlock with the file list
    file_list_block = MarkdownBlock(file_list_message)

    # Add the file list as an enrichment
    event.add_enrichment(MarkdownBlock("*Oh no!* An alert occurred on "))
# returns a pod that mounts the given persistent volume


def persistent_volume_reader(persistent_volume):
    reader_pod_spec = RobustaPod(
        apiVersion="v1",
        kind="Pod",
        metadata=ObjectMeta(
            name="volume-inspector",
            namespace=persistent_volume.spec.claimRef.namespace,
        ),
        spec=PodSpec(
            volumes=[
                Volume(
                    name="pvc-mount",
                    persistentVolumeClaim=PersistentVolumeClaimVolumeSource(
                        claimName=persistent_volume.spec.claimRef.name
                    ),
                )
            ],
            containers=[
                Container(
                    name="pvc-inspector",
                    image="busybox",
                    command=["tail"],
                    args=["-f", "/dev/null"],
                    volumeMounts=[
                        VolumeMount(
                            mountPath="/pvc",
                            name="pvc-mount",
                        )
                    ],
                )
            ],
        ),
    )
    reader_pod = reader_pod_spec.create()
    return reader_pod


# function to get pod data related to a pvc


def get_pod_related_to_pvc(pvc_obj, pv_obj):
    pod_list = PodList.listNamespacedPod(pvc_obj.metadata.namespace).obj
    pod = None
    for pod in pod_list.items:
        for volume in pod.spec.volumes:
            if volume.persistentVolumeClaim:
                if volume.persistentVolumeClaim.claimName == pv_obj.spec.claimRef.name:
                    return pod

