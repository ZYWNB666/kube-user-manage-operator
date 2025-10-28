import yaml
import sys
import subprocess

# 获取命令行参数 service account name
sa_name = sys.argv[1]

# 读取 init-secret.yaml 文件
with open('init-conf/init-secret.yaml', 'r') as file01:
    secret = yaml.safe_load(file01)
# secret name
secret['metadata']['name'] = sa_name
# secret 绑定 account
secret['metadata']['annotations']['kubernetes.io/service-account.name'] = sa_name
# 保存新 secret.yaml 文件
with open('init-conf/tmp-secret.yaml', 'w') as file:
    yaml.dump(secret, file, default_flow_style=False)
create_secret_command = ['kubectl', 'create', '-f', 'init-conf/tmp-secret.yaml']
create_secret = subprocess.run(create_secret_command, capture_output=True, text=True)

# 获取 service account token
kubectl_command = ['kubectl', 'get', 'secret', sa_name, '-n', 'kube-system', '-o', "jsonpath={.data.token}"]
base64_command = ['base64', '--decode']
process1 = subprocess.Popen(kubectl_command, stdout=subprocess.PIPE)
process2 = subprocess.Popen(base64_command, stdin=process1.stdout, stdout=subprocess.PIPE)
process1.stdout.close()
output, error = process2.communicate()
sa_token = output.decode('utf-8')

# 读取 init-kubeconfig.yaml 文件
with open('init-conf/init-kubeconfig.yaml', 'r') as file:
    config = yaml.safe_load(file)
# context user
config['contexts'][0]['context']['user'] = sa_name
# context name
config['contexts'][0]['name'] = config['contexts'][0]['context']['user'] + '@' + config['contexts'][0]['context']['cluster']
# current context
config['current-context'] = config['contexts'][0]['name']
# user name
config['users'][0]['name'] = sa_name
# user token
config['users'][0]['user']['token'] = sa_token

# 输出新 yaml
yaml_str = yaml.dump(config, default_flow_style=False, sort_keys=False)
print('---\n'+yaml_str)

# 将修改后的数据写入新的 YAML 文件
# file name
new_file_name = 'output-kubeconfig/' + config['current-context'] + '.yaml'
with open(new_file_name, 'w') as file:
    yaml.dump(config, file, default_flow_style=False)
