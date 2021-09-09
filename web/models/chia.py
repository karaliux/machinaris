import json
import os
import traceback

import datetime

from web import app
from web.actions import worker as w
from common.utils import converters

# Treat *.plot files smaller than this as in-transit (copying) so don't count them
MINIMUM_K32_PLOT_SIZE_BYTES = 100 * 1024 * 1024

class FarmSummary:

    def __init__(self, farms):
        self.status = "-"
        self.plot_count = 0
        self.plots_size = 0
        self.total_chia = 0
        self.total_flax = 0
        self.netspace_size = 0
        self.flax_netspace_size = 0
        self.netspace_display_size = "-"
        self.flax_netspace_display_size = "-"
        self.expected_time_to_win = "-"
        self.flax_expected_time_to_win = "-"
        for farm in farms:  # Only consider farm info from fullnode
            if farm.mode == "fullnode":
                self.plot_count = farm.plot_count
                self.plots_size = farm.plots_size
                self.status = farm.status
                self.total_chia = '0.0' if not farm.total_chia else round(farm.total_chia, 6)
                self.netspace_display_size = '?' if not farm.netspace_size else converters.gib_to_fmt(farm.netspace_size)
                self.netspace_size = farm.netspace_size
                self.expected_time_to_win = farm.expected_time_to_win
                self.total_flax =  '0.0' if not farm.total_flax else round(farm.total_flax, 6)
                self.flax_netspace_display_size = '?' if not farm.flax_netspace_size else converters.gib_to_fmt(farm.flax_netspace_size)
                self.flax_netspace_size = farm.flax_netspace_size
                self.flax_expected_time_to_win = farm.flax_expected_time_to_win
        self.plots_display_size = converters.gib_to_fmt(self.plots_size)
        self.calc_status(self.status)

    def calc_status(self, status):
        self.status = status
        if self.status == "Farming":
            self.display_status = "Active"
        else:
            self.display_status = self.status

class FarmPlots:

     def __init__(self, plots):
        self.columns = ['worker', 'plot_id',  'dir', 'plot', 'type', 'create_date', 'size' ]
        self.rows = []
        displaynames = {}
        for plot in plots:
            if plot.hostname in displaynames:
                displayname = displaynames[plot.hostname]
            else: # Look up displayname
                try:
                    app.logger.debug("Found worker with hostname with hostname '{0}'".format(plot.hostname))
                    displayname = w.get_worker_by_hostname(plot.hostname).displayname
                except:
                    app.logger.info("Unable to find a worker with hostname '{0}'".format(plot.hostname))
                    displayname = plot.hostname
                displaynames[plot.hostname] = displayname
            self.rows.append({ \
                'worker': displayname, \
                'plot_id': plot.plot_id, \
                'dir': plot.dir,  \
                'plot': plot.file,  \
                'create_date': plot.created_at, \
                'size': plot.size, \
                'type': plot.type if plot.type else "" }) 


class ChallengesChartData:

    def __init__(self, challenges):
        self.labels = []
        datasets = {}
        for challenge in challenges:
            created_at = challenge.created_at.replace(' ', 'T')
            if not created_at in self.labels:
                self.labels.append(created_at)
            host_chain = challenge.hostname + '_' + challenge.blockchain
            if not host_chain in datasets:
                datasets[host_chain] = {}
            dataset = datasets[host_chain]
            dataset[created_at] = float(challenge.time_taken.split()[0]) # Drop off the 'secs'
        # Now build a sparse array with null otherwise
        self.data = {}
        for key in datasets.keys():
            self.data[key] = [] 
        for label in self.labels:
            for key in datasets.keys():
                if label in datasets[key]:
                    self.data[key].append(datasets[key][label])
                else:
                    self.data[key].append('null') # Javascript null

class Wallets:

    def __init__(self, wallets):
        self.columns = ['hostname', 'details', 'updated_at']
        self.rows = []
        for wallet in wallets:
            updated_at = wallet.updated_at or datetime.datetime.now()
            self.rows.append({ 
                'hostname': wallet.hostname, 
                'blockchain': wallet.blockchain, 
                'details': wallet.details, 
                'updated_at': wallet.updated_at }) 

class Keys:

    def __init__(self, keys):
        self.columns = ['hostname', 'details', 'updated_at']
        self.rows = []
        for key in keys:
            self.rows.append({ 
                'hostname': key.hostname, 
                'details': key.details,
                'updated_at': key.updated_at }) 

class Blockchains:

    def __init__(self, blockchains):
        self.columns = ['hostname', 'blockchain', 'details', 'updated_at']
        self.rows = []
        for blockchain in blockchains:
            self.rows.append({ 
                'hostname': blockchain.hostname, 
                'blockchain': blockchain.blockchain, 
                'details': blockchain.details,
                'updated_at': blockchain.updated_at }) 
            
class PartialsChartData:

    def __init__(self, partials):
        self.labels = []
        label_index_by_hour = {}
        for i in range(1,25):
            start_time = datetime.datetime.now().replace(microsecond=0, second=0, minute=0) - datetime.timedelta(hours=24-i)
            self.labels.append(start_time.strftime("%I %p"))
            label_index_by_hour[start_time.strftime("%H")] = len(self.labels) - 1
            #app.logger.info("At {0} is label: {1}".format((len(self.labels) - 1), start_time.strftime("%I %p")))
        self.data = {}
        for partial in partials:
            created_at = partial.created_at
            pool_launcher = partial.pool_url.replace('https://', '') + ' (' + partial.launcher_id[:8] + '...)'
            if not pool_launcher in self.data:
                self.data[pool_launcher] = [0] * 24 # Initialize as list of zeros
            dataset = self.data[pool_launcher]
            partial_hour_at = created_at[11:13]
            #app.logger.info("{0}: partial_hour_at={1} -> slot {2}".format(created_at, partial_hour_at, label_index_by_hour[partial_hour_at]))
            dataset[label_index_by_hour[partial_hour_at]] += 1

    
class Connections:

    def __init__(self, connections):
        self.rows = []
        for connection in connections:
            self.rows.append({
                'hostname': connection.hostname,
                'blockchain': connection.blockchain,
                'protocol_port': '8444' if connection.blockchain == 'chia' else '6888',
                'details': connection.details
            })
    
    def parse(connections):
        # TODO Deal with connection listing from multiple machines
        connection = connections[0]
        self.conns = []
        for line in connection.details.split('\n'):
            try:
                if line.strip().startswith('Connections:'):
                    pass
                elif line.strip().startswith('Type'):
                    self.columns = line.lower().replace('last connect', 'last_connect') \
                        .replace('mib up|down', 'mib_up mib_down').strip().split()
                elif line.strip().startswith('-SB Height'):
                    pass
                else:
                    vals = line.strip().split()
                    #app.logger.debug(vals)
                    self.conns.append({
                        'type': vals[0],
                        'ip': vals[1],
                        'ports': vals[2],
                        'nodeid': vals[3].replace('...',''),
                        'last_connect': datetime.datetime.strptime( \
                            str(datetime.datetime.today().year) + ' ' + vals[4] + ' ' + vals[5] + ' ' + vals[6], 
                            '%Y %b %d %H:%M:%S'),
                        'mib_up': float(vals[7].split('|')[0]),
                        'mib_down': float(vals[7].split('|')[1])
                    })
            except:
                app.logger.info(traceback.format_exc())


class Plotnfts:

    def __init__(self, plotnfts):
        self.columns = ['hostname', 'details', 'updated_at']
        self.rows = []
        for plotnft in plotnfts:
            updated_at = plotnft.updated_at or datetime.datetime.now()
            self.rows.append({ 
                'hostname': plotnft.hostname, 
                'blockchain': plotnft.blockchain, 
                'details': plotnft.details, 
                'updated_at': plotnft.updated_at })
    
    def get_current_pool_url(self):
        pool_url = None
        for row in self.rows:
            for line in row['details'].split('\n'):
                if "Current pool URL:" in line:
                    pool_url = line[len("Current pool URL:"):].strip()
                elif "Target state: SELF_POOLING" in line:
                    return None  # Switching back to self-pooling, no pool_url
        return pool_url

class Pools:

    def __init__(self, pools, plotnfts):
        self.columns = ['hostname', 'blockchain', 'pool_state', 'updated_at']
        self.rows = []
        for pool in pools:
            launcher_id = pool.launcher_id
            plotnft = self.find_plotnft(plotnfts, launcher_id)
            updated_at = pool.updated_at or datetime.datetime.now()
            pool_state = json.loads(pool.pool_state)
            if plotnft:
                status = self.extract_plotnft_value(plotnft, "Current state:")
                points_successful_last_24h = self.extract_plotnft_value(plotnft, "Percent Successful Points (24h)")
            else:
                status = "-"
                pool_errors_24h = len(pool_state['pool_errors_24h'])
                points_found_24h = len(pool_state['points_found_24h'])
                points_successful_last_24h = "%.2f"% ( (points_found_24h - pool_errors_24h) / points_found_24h * 100)
            self.rows.append({ 
                'hostname': pool.hostname,
                'launcher_id': pool.launcher_id, 
                'login_link': pool.login_link, 
                'blockchain': pool.blockchain, 
                'pool_state': pool_state,
                'updated_at': pool.updated_at,
                'status': status,
                'points_successful_last_24h': points_successful_last_24h
            })
    
    def find_plotnft(self, plotnfts, launcher_id):
        for plotnft in plotnfts:
            if launcher_id in plotnft.details:
                return plotnft
        return None

    def extract_plotnft_value(self, plotnft, key):
        for line in plotnft.details.splitlines():
            if line.startswith(key):
                return line[line.index(':')+1:].strip()
        return None