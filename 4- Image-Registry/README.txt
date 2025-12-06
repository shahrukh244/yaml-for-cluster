## Setup Docker Image Registry ##


#####

On Bastion node install docker


# Update package index
sudo apt-get update

# Install required packages
sudo apt-get install -y apt-transport-https ca-certificates curl gnupg-agent software-properties-common

# Add Docker’s official GPG key
curl -fsSL https://download.docker.com/linux/ubuntu/gpg  | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Add Docker APT repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Update package index again
sudo apt-get update

# Install Docker Engine
sudo apt-get install -y docker-ce docker-ce-cli containerd.io

# Verify Docker is installed
sudo docker --version

# Make this entry
vi /etc/docker/daemon.json
{
  "insecure-registries": ["registry.kube.lan"]
}


systemctl restart docker


#####

kubectl apply -f namespace.yaml

kubectl apply -f registry-pvc.yaml

kubectl apply -f registry-deployment.yaml

kubectl apply -f registry-service.yaml

kubectl get ingress -n registry
kubectl get svc -n registry
kubectl get svc -n ingress-nginx


# Add DNS entry in SVC node
10.0.0.1 registry.kube.lan


# Add Haproxy entry in SVC node
# /etc/haproxy/haproxy.cnf

backend registry_http_backend
    mode http
    balance roundrobin
    server kube-w-1 10.0.0.211:31041 check
    server kube-w-2 10.0.0.212:31041 check

backend registry_https_backend
    mode http
    balance roundrobin
    server kube-w-1 10.0.0.211:31212 check
    server kube-w-2 10.0.0.212:31212 check




systemctl restart haproxy
systemctl status haproxy


# Test registry
curl -v http://registry.kube.lan/v2/


docker pull nginx
docker tag nginx registry.kube.lan/nginx
docker push registry.kube.lan/nginx







