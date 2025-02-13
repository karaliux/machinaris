#!/bin/env bash
#
# Initialize Flax service, depending on mode of system requested
#

cd /flax-blockchain

. ./activate

# Only the /root/.chia folder is volume-mounted so store flax within
mkdir -p /root/.chia/flax
rm -f /root/.flax
ln -s /root/.chia/flax /root/.flax 

mkdir -p /root/.flax/mainnet/log
flax init >> /root/.flax/mainnet/log/init.log 2>&1 

if [[ "${blockchain_db_download}" == 'true' ]] \
  && [[ "${mode}" == 'fullnode' ]] \
  && [[ -f /usr/bin/mega-get ]] \
  && [[ ! -f /root/.flax/mainnet/db/blockchain_v1_mainnet.sqlite ]]; then
  echo "Downloading Flax blockchain DB (many GBs in size) on first launch..."
  echo "Please be patient as takes minutes now, but saves days of syncing time later."
  mkdir -p /root/.flax/mainnet/db/ && cd /root/.flax/mainnet/db/
  # Mega links for Flax blockchain DB from: https://chiaforksblockchain.com/
  mega-get https://mega.nz/folder/WBpCARSA#REDq1mKfsyWjLSEJdgPoaA
  mv flax/*.sqlite . && rm -rf flax
fi

echo 'Configuring Flax...'
if [ -f /root/.flax/mainnet/config/config.yaml ]; then
  sed -i 's/log_stdout: true/log_stdout: false/g' /root/.flax/mainnet/config/config.yaml
  sed -i 's/log_level: WARNING/log_level: INFO/g' /root/.flax/mainnet/config/config.yaml
  sed -i 's/localhost/127.0.0.1/g' /root/.flax/mainnet/config/config.yaml
fi

# Loop over provided list of key paths
for k in ${keys//:/ }; do
  if [[ "${k}" == "persistent" ]]; then
    echo "Not touching key directories."
  elif [ -s ${k} ]; then
    echo "Adding key at path: ${k}"
    flax keys add -f ${k} > /dev/null
  fi
done

# Loop over provided list of completed plot directories
for p in ${plots_dir//:/ }; do
  flax plots add -d ${p}
done

chmod 755 -R /root/.flax/mainnet/config/ssl/ &> /dev/null
flax init --fix-ssl-permissions > /dev/null 

# Start services based on mode selected. Default is 'fullnode'
if [[ ${mode} == 'fullnode' ]]; then
  for k in ${keys//:/ }; do
    while [[ "${k}" != "persistent" ]] && [[ ! -s ${k} ]]; do
      echo 'Waiting for key to be created/imported into mnemonic.txt. See: http://localhost:8926'
      sleep 10  # Wait 10 seconds before checking for mnemonic.txt presence
      if [ -s ${k} ]; then
        flax keys add -f ${k}
        sleep 10
      fi
    done
  done
  flax start farmer
elif [[ ${mode} =~ ^farmer.* ]]; then
  if [ ! -f ~/.flax/mainnet/config/ssl/wallet/public_wallet.key ]; then
    echo "No wallet key found, so not starting farming services.  Please add your Chia mnemonic.txt to the ~/.machinaris/ folder and restart."
  else
    flax start farmer-only
  fi
elif [[ ${mode} =~ ^harvester.* ]]; then
  if [[ -z ${farmer_address} || -z ${farmer_port} ]]; then
    echo "A farmer peer address and port are required."
    exit
  else
    if [ ! -f /root/.flax/farmer_ca/private_ca.crt ]; then
      mkdir -p /root/.flax/farmer_ca
      response=$(curl --write-out '%{http_code}' --silent http://${farmer_address}:8928/certificates/?type=flax --output /tmp/certs.zip)
      if [ $response == '200' ]; then
        unzip /tmp/certs.zip -d /root/.flax/farmer_ca
      else
        echo "Certificates response of ${response} from http://${farmer_address}:8928/certificates/?type=flax.  Try clicking 'New Worker' button on 'Workers' page first."
      fi
      rm -f /tmp/certs.zip 
    fi
    if [ -f /root/.flax/farmer_ca/private_ca.crt ]; then
      flax init -c /root/.flax/farmer_ca 2>&1 > /root/.flax/mainnet/log/init.log
      chmod 755 -R /root/.flax/mainnet/config/ssl/ &> /dev/null
      flax init --fix-ssl-permissions > /dev/null 
    else
      echo "Did not find your farmer's certificates within /root/.flax/farmer_ca."
      echo "See: https://github.com/guydavis/machinaris/wiki/Workers#harvester"
    fi
    flax configure --set-farmer-peer ${farmer_address}:${farmer_port}
    flax configure --enable-upnp false
    flax start harvester -r
  fi
elif [[ ${mode} == 'plotter' ]]; then
    echo "Starting in Plotter-only mode.  Run Plotman from either CLI or WebUI."
fi
