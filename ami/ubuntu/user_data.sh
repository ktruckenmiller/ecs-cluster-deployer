
# apt-get update && apt-get install linux-image-extra-$(uname -r) linux-image-extra-virtual
apt-get update && apt-get install jq nfs-common python-pip linux-image-extra-virtual apt-transport-https ca-certificates curl software-properties-common -y
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
apt-key fingerprint 0EBFCD88
add-apt-repository \
   "deb [arch=amd64] https://download.docker.com/linux/ubuntu \
   $(lsb_release -cs) \
   stable"

apt-get update && apt-get install docker-ce -y
systemctl stop docker
cat <<'EOF' >> /etc/docker/daemon.json
{
  "storage-driver": "overlay2"
}
EOF

#ecs stuff
sh -c "echo 'net.ipv4.conf.all.route_localnet = 1' >> /etc/sysctl.conf"
sysctl -p /etc/sysctl.conf
iptables -t nat -A PREROUTING -p tcp -d 169.254.170.2 --dport 80 -j DNAT --to-destination 127.0.0.1:51679
iptables -t nat -A OUTPUT -d 169.254.170.2 -p tcp -m tcp --dport 80 -j REDIRECT --to-ports 51679
mkdir /etc/iptables && iptables-save > /etc/iptables/rules.v4

# Set up ecs
mkdir -p /etc/ecs
cat <<'EOF' >> /etc/ecs/ecs.config
ECS_DATADIR=/data
ECS_ENABLE_TASK_IAM_ROLE=true
ECS_ENABLE_TASK_IAM_ROLE_NETWORK_HOST=true
ECS_LOGFILE=/log/ecs-agent.log
ECS_AVAILABLE_LOGGING_DRIVERS=["json-file","awslogs"]
ECS_LOGLEVEL=info
ECS_CLUSTER=webapp
EOF

mkdir -p /var/log/ecs /var/lib/ecs/data
