
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
def volume_analysis6(event: PersistentVolumeEvent):
    Persistent_Volume = event.get_persistentvolume()
    api = client.CoreV1Api()
    Persistent_Volume_Name = Persistent_Volume.metadata.name
    Persistent_Volume_Details = api.read_persistent_volume(Persistent_Volume_Name)
    print("PV",Persistent_Volume_Details)
    if Persistent_Volume_Details.spec.claim_ref is not None:
        PVC_Name = Persistent_Volume_Details.spec.claim_ref.name
        PVC_NameSpace = Persistent_Volume_Details.spec.claim_ref.namespace
        print(PVC_Name)
        print(PVC_NameSpace)
        Pod = get_pod_attached_to_pvc(api, PVC_Name, PVC_NameSpace)

        #print(Pod)
        mountedVolumeName = None  # Initialize the variable
        for volume in Pod.spec.volumes:
            if volume.persistent_volume_claim and volume.persistent_volume_claim.claim_name == PVC_Name:
                mountedVolumeName = volume.name
        for containers in Pod.spec.containers:
            #container_name=Pod.containers.name
            if containers.volume_mounts[0].name == mountedVolumeName:
                podMountPath = containers.volume_mounts[0].mount_path  # We have a volume Path
                new_podMountPath = podMountPath[1:]
                print("New path ", new_podMountPath)
                #break
        namespace = "default"
        pod_name = "new-pv-pod"
        podR = RobustaPod(pod_name, namespace)
        print(podR)
        # Define the command to run inside the Pod
        command = "ls -R"

        try:
            # Execute the command inside the Pod
            output = podR.exec_command(command)

            # Print the command output
            print("Command Output:")
            print(output)

        except Exception as e:
            print(f"Error executing command in Pod: {str(e)}")
    else:
        event.add_enrichment([
            MarkdownBlock("No PVC is attached to the PV named " + Persistent_Volume_Name)
        ])


def get_pod_attached_to_pvc(api, pvc_name, pvc_namespace):
    try:
        pvc = api.read_namespaced_persistent_volume_claim(pvc_name, pvc_namespace)
        if pvc.spec.volume_name:
            pod_list = api.list_namespaced_pod(pvc_namespace)
            for pod in pod_list.items:
                for volume in pod.spec.volumes:
                    if volume.persistent_volume_claim and volume.persistent_volume_claim.claim_name == pvc_name:
                        return pod
    except client.exceptions.ApiException as e:
        print(f"Error: {e}")
    return None


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


def exec_commands(api_instance):
    name = 'busybox-test'
    resp = None
    try:
        resp = api_instance.read_namespaced_pod(name=name,
                                                namespace='default')
    except ApiException as e:
        if e.status != 404:
            print(f"Unknown error: {e}")
            exit(1)

    if not resp:
        print(f"Pod {name} does not exist. Creating it...")
        pod_manifest = {
            'apiVersion': 'v1',
            'kind': 'Pod',
            'metadata': {
                'name': name
            },
            'spec': {
                'containers': [{
                    'image': 'busybox',
                    'name': 'sleep',
                    "args": [
                        "/bin/sh",
                        "-c",
                        "while true;do date;sleep 5; done"
                    ]
                }]
            }
        }
        resp = api_instance.create_namespaced_pod(body=pod_manifest,
                                                  namespace='default')
        while True:
            resp = api_instance.read_namespaced_pod(name=name,
                                                    namespace='default')
            if resp.status.phase != 'Pending':
                break
            time.sleep(1)
        print("Done.")

    # Calling exec and waiting for response
    exec_command = [
        '/bin/sh',
        '-c',
        'echo This message goes to stderr; echo This message goes to stdout']
    # When calling a pod with multiple containers running the target container
    # has to be specified with a keyword argument container=<name>.
    resp = stream(api_instance.connect_get_namespaced_pod_exec,
                  name,
                  'default',
                  command=exec_command,
                  stderr=True, stdin=False,
                  stdout=True, tty=False)
    print("Response: " + resp)

    # Calling exec interactively
    exec_command = ['/bin/sh']
    resp = stream(api_instance.connect_get_namespaced_pod_exec,
                  name,
                  'default',
                  command=exec_command,
                  stderr=True, stdin=True,
                  stdout=True, tty=False,
                  _preload_content=False)
    commands = [
        "echo This message goes to stdout",
        "echo \"This message goes to stderr\" >&2",
    ]

    while resp.is_open():
        resp.update(timeout=1)
        if resp.peek_stdout():
            print(f"STDOUT: {resp.read_stdout()}")
        if resp.peek_stderr():
            print(f"STDERR: {resp.read_stderr()}")
        if commands:
            c = commands.pop(0)
            print(f"Running command... {c}\n")
            resp.write_stdin(c + "\n")
        else:
            break

    resp.write_stdin("date\n")
    sdate = resp.readline_stdout(timeout=3)
    print(f"Server date command returns: {sdate}")
    resp.write_stdin("whoami\n")
    user = resp.readline_stdout(timeout=3)
    print(f"Server user is: {user}")
    resp.close()