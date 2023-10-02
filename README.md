# Robusta Specialization Module (Custom Playbook Actions)
## Task 1: Setup Kubernetes cluster in your local machine using Kind
1. Install the kinD cluster.
```bash
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.11.1/kind-linux-amd64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/
kind version
```
2. Install kubectl.
```bash
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl
sudo mv kubectl /usr/local/bin/
kubectl version --client
```
3. Create a cluster and verify it.
```bash
kind create cluster
kubectl get nodes
```

## Task 2: Install Robusta on your Kubernetes cluster
1. Create python environment.
```bash
python3.10 -m venv robusta
source robusta/bin/activate
```
2. Install the robusta-cli: This step is needed to generate the values file for helm chart installation.
```bash
python3 -m pip install -U robusta-cli --no-cache
```
3. Generate a generated_values.yaml for the Robusta chart:
```bash
# An interactive session where you can configure sinks 
# such as receiving alerts to a particular Slack channel, MS Teams. 
# This generates a `generated_values.yaml`
robusta gen-config
```
3. Install Robusta with helm:
```bash
helm repo add robusta https://robusta-charts.storage.googleapis.com && helm repo update
helm install robusta robusta/robusta -f ./generated_values.yaml --set clusterName=<cluster-name>
```

## Task 3: Deploy a Pod on your Kubernetes cluster which uses a persistent volume
1. Deploy a manifest with PV, PVC and Pod.
```bash
kubectl apply -f Scenario_1.yaml
```
## Task 4: Create your [playbook repository](https://docs.robusta.dev/master/developer-guide/actions/playbook-repositories.html), push that to GitHub and use the Github link in your Robusta's generated-values.yaml file.
1. Add the following code in the generated.yaml file after setting up the repository.
```bash
playbookRepos:
  my_extra_playbooks:
    url: https://github.com/HamzaXgrid/RobustaPlaybook1.git
playbooksPersistentVolume: true
customPlaybooks:
- triggers:
  - on_pod_update: {}
  actions:
  - my_action: {}
```
2. Now update the values in the helm.
```bash
helm upgrade robusta robusta/robusta --values=generated_values.yaml --set clusterName=kind-mycluster-1
```
3. Invoke a trigger using below command.
```bash
robusta playbooks trigger on_pod_update
```
## Task 5: Write a function on python which mounts a persistent volume and send the list of files present on that persistent volume to a sink.
It is somewhat like Zapier/IFTTT for devops, with an emphasis on prebuilt automations and not just "build your own".
## Task 6: Make sure to cover all scenarios
## Task 7: Run the action using your generated-values.yaml file and manually.
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