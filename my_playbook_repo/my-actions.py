
import logging
from kubernetes import client
from hikaru.model.rel_1_26 import *
from robusta.api import *

@action
def List_of_Files_on_PV(event: PersistentVolumeEvent):
    finding = Finding(
        title="Persistent Volume content",
        source=FindingSource.MANUAL,
        aggregation_key="List_of_Files_on_PV",
    )
    if not event.get_persistentvolume():
        logging.error(f"VolumeAnalysis was called on event without Persistent Volume: {event}")
        return
    Persistent_Volume = event.get_persistentvolume()
    api = client.CoreV1Api()
    Persistent_Volume_Name = Persistent_Volume.metadata.name
    Persistent_Volume_Details = api.read_persistent_volume(Persistent_Volume_Name)
    if Persistent_Volume_Details.spec.claim_ref is not None:# We are checking whether PV is claimed by any PVC.
        PVC_Name = Persistent_Volume_Details.spec.claim_ref.name
        PVC_NameSpace = Persistent_Volume_Details.spec.claim_ref.namespace
        print(PVC_Name)
        print(PVC_NameSpace)
        Pod = pods_PVC(api, PVC_Name, PVC_NameSpace)
        if Pod==None:# If no Pod claims any PVC than creates a temporary pod
            temp_pod = Temp_Pod(persistent_volume=Persistent_Volume)
            result = temp_pod.exec(f"ls -R {temp_pod.spec.containers[0].volumeMounts[0].mountPath}/")
            finding.title = f"Persistent Volume Content:"
            finding.add_enrichment(
                [
                    MarkdownBlock("Data on the PV "),
                    FileBlock("Data.txt: ", result.encode()),
                ]
                )
            event.add_finding(finding)
            if temp_pod is not None: # Deletes the Temporary Pod, This is necessary step as we don't want unused resources in our cluster
                print("Deleting the pod")
                temp_pod.delete()
                return
        else:
            mountedVolumeName = None  # Initialize the variable  
            for volume in Pod.spec.volumes:
                if volume.persistent_volume_claim and volume.persistent_volume_claim.claim_name == PVC_Name:
                    mountedVolumeName = volume.name
            for containers in Pod.spec.containers:
                #container_name=Pod.containers.name
                for volumes in containers.volume_mounts:
                    if volumes.name == mountedVolumeName:
                        podMountPath = containers.volume_mounts[0].mount_path  # We have a volume Path
                        new_podMountPath = podMountPath[1:] #Removing the Slash from the Mountpath, This part is only necessary if we are executing find command inside the pod instead of ls
                        #break
            namespace = PVC_NameSpace
            pod_name = Pod.metadata.name
            POD1=get_pod_to_exec_Command(pod_name,namespace)
            List_of_Files = POD1.exec(f"ls -R {new_podMountPath}/")
            event.add_enrichment([
                MarkdownBlock("The Name of The PV is "  + mountedVolumeName),
                FileBlock("FilesList.log", List_of_Files)
            ])
            finding.title = f"Persistent Volume Content: "
            finding.add_enrichment(
                [
                    FileBlock("Data.txt: ", List_of_Files.encode()),
                ]
            )
    else:
        finding.title = f"Persistent Volume Content: "
        event.add_enrichment([
            MarkdownBlock("PV is not claimed by any PVC"),
        ])
        event.add_finding(finding)


def pods_PVC(api, pvc_name, pvc_namespace):#Returns the POD that claimed the PVC passed in the function
    try:
        pvc = api.read_namespaced_persistent_volume_claim(pvc_name, pvc_namespace)
        if pvc.spec.volume_name:
            print("Volume Name is ",pvc.spec.volume_name)
            pod_list = api.list_namespaced_pod(pvc_namespace)
            for pod in pod_list.items:
                for volume in pod.spec.volumes:
                    if volume.persistent_volume_claim and volume.persistent_volume_claim.claim_name == pvc_name:
                        return pod
    except client.exceptions.ApiException as e:
        print(f"Error: {e}")
    return None

def Temp_Pod(persistent_volume):#Creates a temporary Pod and attached the pod with the PVC
    Volumes=[Volume(name="pvc-mount",
                    persistentVolumeClaim=PersistentVolumeClaimVolumeSource(
                        claimName=persistent_volume.spec.claimRef.name
                    ),
                )
            ]
    Containers=[
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
            ]
    Pod_Spec = RobustaPod(
        apiVersion="v1",
        kind="Pod",
        metadata=ObjectMeta(
            name="volume-inspector",
            namespace=persistent_volume.spec.claimRef.namespace,
        ),
        spec=PodSpec(
            volumes=Volumes,
            containers=Containers,
        ),
    )
    Temp_pod = Pod_Spec.create()
    return Temp_pod

def get_pod_to_exec_Command(pod_name,pod_namespace): #Returns the Pod with Specific name
    pod_list = PodList.listNamespacedPod(pod_namespace).obj
    pod = None
    for pod in pod_list.items:
        if pod_name==pod.metadata.name:
            return pod
    return pod








