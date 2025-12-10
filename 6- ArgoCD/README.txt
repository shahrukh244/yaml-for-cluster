
kubectl apply -f 00-namespace.yaml

curl -L https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml -o 01-install.yaml

kubectl apply -f 01-install.yaml

kubectl apply -f 02-redis-pvc.yaml

kubectl patch deployment argocd-redis -n argocd --patch-file 03-redis-deployment-patch.yaml

kubectl rollout restart deployment argocd-redis -n argocd

kubectl apply -f 04-ingress.yaml




# Add this line in comfigmap
kubectl -n argocd get configmap argocd-cmd-params-cm -o yaml > configmap.yaml

data:
  server.insecure: "true"

vi configmap.yaml

# Example Add at the end of file

  resourceVersion: "236781"
  uid: e805b2d4-998d-4afc-b159-8d1da5312095
data:
  server.insecure: "true"


kubectl rollout restart deployment argocd-server -n argocd




## Get ArgoCD admin Password ###

kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d ; echo


https://argocd.kube.lan
Username: admin
Password: <output of the command above>

