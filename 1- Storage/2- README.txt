
NFS-Server Should Already Configured And Running Only Then Run This...

showmount -e  10.0.0.1


 
# Ensure repo is up-to-date
helm repo update



# Verify version 
helm search repo csi-driver-nfs



# Install latest version (4.12.1 as of now)
helm install csi-driver-nfs csi-driver-nfs/csi-driver-nfs \
  --namespace kube-system \
  --version 4.12.1 \
  --set node.selector="kubernetes.io/os=linux" \
  --create-namespace



# Verify Installation
kubectl get pods -n kube-system -l app.kubernetes.io/name=csi-driver-nfs
kubectl get csidrivers nfs.csi.k8s.io
helm list -n kube-system | grep csi-driver-nfs



_________________________________________________________________________________________





Create Storage Class

# kubectl apply -f storageclass-Delete.yaml
# kubectl apply -f storageclass-Retain.yaml

# kubectl get sc

# kubectl describe sc nfs-delete
# kubectl describe sc nfs-retain





Test Storage Class (Delete)

# kubectl apply -f teststorageclass-delete.yaml

# kubectl get pvc -n testing01
# kubectl get pods -n testing01

# kubectl exec -n testing01 -it nfs-test-pod -- cat /data/hello.txt

