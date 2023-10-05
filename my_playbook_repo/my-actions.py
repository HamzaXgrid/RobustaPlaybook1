
import logging
from kubernetes import client, config
from hikaru.model.rel_1_26 import (
    Container,
    ObjectMeta,
    PersistentVolumeClaim,
    PersistentVolumeClaimVolumeSource,
    PodList,
    PodSpec,
    Volume,
    VolumeMount,
)
from robusta.api import (
    FileBlock,
    Finding,
    FindingSource,
    FindingType,
    MarkdownBlock,
    PersistentVolumeEvent,
    RobustaPod,
    action,
)
import os
from robusta.api import *
import subprocess


from robusta.api import *

@action
def my_action(event: PodEvent):
    # we have full access to the pod on which the alert fired
    pod = event.get_pod()
    pod_name = pod.metadata.name
    pod_logs = pod.get_logs()
    pod_processes = pod.exec("ps aux")

    # this is how you send data to slack or other destinations
    event.add_enrichment([
        MarkdownBlock("*Oh no!* An alert occurred on " + pod_name),
        FileBlock("crashing-pod.log", pod_processes)
    ])
@action
def volume_analysis1(event: PersistentVolumeEvent):
    pv = event.get_persistentvolume()
    print("pv is ",pv)
    pvc=get_pvc_attached_to_pv(pv)
    print("pvc is ",pvc)
    if pv.spec.claimRef is not none:
        print("Claim is ",pv.spec.claimRef)
        pvc_obj = PersistentVolumeClaim.readNamespacedPersistentVolumeClaim(
                name=pv_claimref.name, namespace=pv_claimref.namespace
            ).obj
    event.add_enrichment([
        MarkdownBlock("*Oh no!* An alert occurred on " + pv + pvc_obj)
    ])

def get_pvc_attached_to_pv(pv_name):
    try:
    
        os.environ['KUBECONFIG'] = '/root/.kube/config'
        config.load_kube_config()
        api = client.CoreV1Api()
        pv = api.read_persistent_volume(pv_name.metadata.name)

        # Check if the PV has a bound PVC
        if pv.spec.claim_ref:
            # Get the PVC using the claimRef information
            pvc_namespace = pv.spec.claim_ref.namespace
            pvc_name = pv.spec.claim_ref.name
            pvc = api.read_namespaced_persistent_volume_claim(pvc_name, pvc_namespace)
            return pvc
        else:
            print(f"No PVC is attached to PV '{pv_name}'")
            return None
    except client.exceptions.ApiException as e:
        print(f"Error: {e}")
        return None
    except client.exceptions.ApiException as e:
        print(f"Error: {e}")
        return None
@action
def volume_analysis(event: PersistentVolumeEvent):
    """
    This action shows you the files present on your persistent volume
    """
    function_name = "volume_analysis"
    # https://docs.robusta.dev/master/extending/actions/findings-api.html
    finding = Finding(
        title="Persistent Volume content",
        source=FindingSource.MANUAL,
        aggregation_key=function_name,
        finding_type=FindingType.REPORT,
        failure=False,
    )

    if not event.get_persistentvolume():
        logging.error(f"VolumeAnalysis was called on event without Persistent Volume: {event}")
        return

    # Get persistent volume data the object contains data related to PV like metadata etc
    pv = event.get_persistentvolume()
    #print("PV is ",pv)
    pv_claimref = pv.spec.claimRef
    #print("pv_claimref is ",pv_claimref)
    reader_pod = None

    try:

        if pv_claimref is not None:
            # Do this if there is a PVC attached to PV
            pvc_obj = PersistentVolumeClaim.readNamespacedPersistentVolumeClaim(
                name=pv_claimref.name, namespace=pv_claimref.namespace
            ).obj
            print("pvc_obj is ",pvc_obj)
            pod = get_pod_related_to_pvc(pvc_obj, pv)
            #print("pod is ",pod)
            if pod is not None:
                # Do this if a Pod is using PVC

                volume_mount_name = None

                # Find name of the mounted volume on pod
                for volume in pod.spec.volumes:
                    if volume.persistentVolumeClaim.claimName == pv_claimref.name:
                        volume_mount_name = volume.name
                        break

                # Use name of the mounted volume to find the correct volume mount
                container_found_flag = False
                container_volume_mount = None
                for container in pod.spec.containers:
                    if container_found_flag:
                        break
                    for volume_mount in container.volumeMounts:
                        if volume_mount_name == volume_mount.name:
                            container_volume_mount = volume_mount
                            container_found_flag = True
                            break
                #print("DATA is")
                #print(container_volume_mount.mountPath)
                result = pod.exec(f"ls -R {container_volume_mount.mountPath}/")  # type: ignore
                finding.title = f"Files present on persistent volume {pv.metadata.name} are: "
                finding.add_enrichment(
                    [
                        FileBlock("Data.txt: ", result.encode()),
                    ]
                )

            else:
                # Do this if no Pod is attached to PVC
                reader_pod = persistent_volume_reader(persistent_volume=pv)
                result = reader_pod.exec(f"ls -R {reader_pod.spec.containers[0].volumeMounts[0].mountPath}")
                finding.title = f"Files present on persistent volume {pv.metadata.name} are: "
                finding.add_enrichment(
                    [
                        FileBlock("Data.txt: ", result.encode()),
                    ]
                )
        else:
            finding.add_enrichment(
                [
                    MarkdownBlock(f"Persistent volume named {pv.metadata.name} have no persistent volume claim."),
                ]
            )

    finally:
        # delete the reader pod
        if reader_pod is not None:
            reader_pod.delete()

    event.add_finding(finding)


@action
def volume_analysis4(event: PersistentVolumeEvent):
    persistent_Volume=event.get_persistentvolume()
    print("The name of the Persisitent Volume is ",persistent_Volume.metadata.name)
    persistent_VolumeName=persistent_Volume.metadata.name
    if persistent_Volume.spec.claimRef is not None: # This tells a volume is claimed by PVC
        persistent_VolumeClaimName=persistent_Volume.spec.claimRef.name
        persistent_VolumeClaimNameSpace=persistent_Volume.spec.claimRef.namespace
        #pv=persistent_Volume.metadata.name
        list_of_Pods=PodList.listNamespacedPod(persistent_VolumeClaimNameSpace).obj
        #print("Pods ARE ",list_of_Pods)
        for pod in list_of_Pods.items: # Iterates over a list of Pods in a namespace
            for volume in pod.spec.volumes: # Iterates over the volume in each Pod to get the pod with a claim name
                if volume.persistentVolumeClaim:
                    if volume.persistentVolumeClaim.claimName == persistent_VolumeClaimName: # Checks for the claim name
                        mountedVolumeName=volume.name # Get the name of the Volume
                        Pod = pod # Gets the POD with PVC
                        for containers in pod.spec.containers:# Iterates over the conatiners
                            for volumePath in containers.volumeMounts: # Iterates over the Volumes mounted on each container
                                if mountedVolumeName == volumePath.name:
                                    podMountPath=volumePath.mountPath # We have a volume Path
                                    new_podMountPath=podMountPath[1:]
                                    print("New path ",new_podMountPath)
                                    break 
        List_of_Files = pod.exec(f"find {new_podMountPath}/ -type f") 
            
        event.add_enrichment([
            MarkdownBlock("The Name of The PV is " + persistent_VolumeName +persistent_VolumeClaimName + persistent_VolumeClaimNameSpace + mountedVolumeName),
            FileBlock("FilesList.log", List_of_Files)
        ])
    else:
        event.add_enrichment([
            MarkdownBlock("No PVC is attached to the PV named " + persistent_VolumeName)
        ])
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
@action
def list_files_on_persistent_volume(event: PersistentVolumeEvent):
    pv = event.get_persistentvolume()

    # Specify the path to the Persistent Volume
    persistent_volume_path = "/usr/share/nginx/html" 
    print(f"Listing files in path: {persistent_volume_path}")

        # List all files in the specified path
    files = os.listdir(persistent_volume_path)
    print("hhhhhhhhhhhhhhhhhh")
    print(f"Listing files in path 1: {files}")
        # Prepare a message with the list of files

        # Add the file list as an enrichment
    event.add_enrichment(MarkdownBlock("Files in the Persistent Volume"))


