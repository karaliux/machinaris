#!/bin/env bash
#
# Initialize Cactus service, depending on mode of system requested
#

cd /cactus-blockchain

. ./activate

# Only the /root/.chia folder is volume-mounted so store cactus within
mkdir -p /root/.chia/cactus
rm -f /root/.cactus
ln -s /root/.chia/cactus /root/.cactus 

mkdir -p /root/.cactus/mainnet/log
cactus init >> /root/.cactus/mainnet/log/init.log 2>&1 

if [[ "${blockchain_db_download}" == 'true' ]] \
  && [[ "${mode}" == 'fullnode' ]] \
  && [[ -f /usr/bin/mega-get ]] \
  && [[ ! -f /root/.cactus/mainnet/db/blockchain_v1_mainnet.sqlite ]]; then
  echo "Downloading Cactus blockchain DB (many GBs in size) on first launch..."
  echo "Please be patient as takes minutes now, but saves days of syncing time later."
  mkdir -p /root/.cactus/mainnet/db/ && cd /root/.cactus/mainnet/db/
  # Mega links for Cactus blockchain DB from: https://chiaforksblockchain.com/
  mega-get https://mega.nz/folder/ON5QkJTI#-ImFLyyhBH_-fwzfqB5iJQ
  mv cactus/*.sqlite . && rm -rf cactus
fi

echo 'Configuring Cactus...'
if [ -f /root/.cactus/mainnet/config/config.yaml ]; then
  sed -i 's/log_stdout: true/log_stdout: false/g' /root/.cactus/mainnet/config/config.yaml
  sed -i 's/log_level: WARNING/log_level: INFO/g' /root/.cactus/mainnet/config/config.yaml
  sed -i 's/localhost/127.0.0.1/g' /root/.cactus/mainnet/config/config.yaml
fi

# Loop over provided list of key paths
for k in ${keys//:/ }; do
  if [[ "${k}" == "persistent" ]]; then
    echo "Not touching key directories."
  elif [ -s ${k} ]; then
    echo "Adding key at path: ${k}"
    cactus keys add -f ${k} > /dev/null
  fi
done

# Loop over provided list of completed plot directories
for p in ${plots_dir//:/ }; do
  cactus plots add -d ${p}
done

#chmod 755 -R /root/.cactus/mainnet/config/ssl/ &> /dev/null
#cactus init --fix-ssl-permissions > /dev/null 

# Start services based on mode selected. Default is 'fullnode'
if [[ ${mode} == 'fullnode' ]]; then
  for k in ${keys//:/ }; do
    while [[ "${k}" != "persistent" ]] && [[ ! -s ${k} ]]; do
      echo 'Waiting for key to be created/imported into mnemonic.txt. See: http://localhost:8926'
      sleep 10  # Wait 10 seconds before checking for mnemonic.txt presence
      if [ -s ${k} ]; then
        cactus keys add -f ${k}
        sleep 10
      fi
    done
  done
  cactus start farmer
elif [[ ${mode} =~ ^farmer.* ]]; then
  if [ ! -f ~/.cactus/mainnet/config/ssl/wallet/public_wallet.key ]; then
    echo "No wallet key found, so not starting farming services.  Please add your Chia mnemonic.txt to the ~/.machinaris/ folder and restart."
  else
    cactus start farmer-only
  fi
elif [[ ${mode} =~ ^harvester.* ]]; then
  if [[ -z ${farmer_address} || -z ${farmer_port} ]]; then
    echo "A farmer peer address and port are required."
    exit
  else
    if [ ! -f /root/.cactus/farmer_ca/private_ca.crt ]; then
      mkdir -p /root/.cactus/farmer_ca
      response=$(curl --write-out '%{http_code}' --silent http://${farmer_address}:8936/certificates/?type=cactus --output /tmp/certs.zip)
      if [ $response == '200' ]; then
        unzip /tmp/certs.zip -d /root/.cactus/farmer_ca
      else
        echo "Certificates response of ${response} from http://${farmer_address}:8936/certificates/?type=cactus.  Try clicking 'New Worker' button on 'Workers' page first."
      fi
      rm -f /tmp/certs.zip 
    fi
    if [ -f /root/.cactus/farmer_ca/private_ca.crt ]; then
      cactus init -c /root/.cactus/farmer_ca 2>&1 > /root/.cactus/mainnet/log/init.log
      #chmod 755 -R /root/.cactus/mainnet/config/ssl/ &> /dev/null
      #cactus init --fix-ssl-permissions > /dev/null 
    else
      echo "Did not find your farmer's certificates within /root/.cactus/farmer_ca."
      echo "See: https://github.com/guydavis/machinaris/wiki/Workers#harvester"
    fi
    cactus configure --set-farmer-peer ${farmer_address}:${farmer_port}
    cactus configure --enable-upnp false
    cactus start harvester -r
  fi
elif [[ ${mode} == 'plotter' ]]; then
    echo "Starting in Plotter-only mode.  Run Plotman from either CLI or WebUI."
fi
