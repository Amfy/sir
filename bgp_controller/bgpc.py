from pydoc import locate
from datetime import datetime, timedelta

import logging
logger = logging.getLogger('sir')

# TODO Send BGP Table

class BGPController:
    def __init__(self, conf):
        self.conf = conf
        backend_class = locate('bgp_controller.backend.%s' % self.conf['backend'])
        self.backend = backend_class(self.conf)

    def run(self):
        logger.info('action=RUN')
        start = datetime.now() - timedelta(hours = self.conf['history'])
        end = datetime.now()

        self.backend.open()
        self.process_prefixes(start, end)
        self.execute_plugins(time=end, simulation=False, last_run=True)
        self.backend.purge_data(end)
        self.backend.close()

    def simulate(self):
        logger.info('action=SIMULATE')
        start = datetime.strptime(self.conf['simulate']['start_date'], self.conf['simulate']['date_format'])
        end = datetime.strptime(self.conf['simulate']['end_date'], self.conf['simulate']['date_format'])

        self.backend.open()

        dates = self.backend.get_available_dates_in_range(start, end)

        iteration = 0
        total_iterations = len(dates)

        for date in dates:
            iteration += 1

            end_date = datetime.strptime(date[0], self.conf['simulate']['date_format'])
            start_date = end_date - timedelta(hours = self.conf['history'])
            self.process_prefixes(start_date, end_date)

            last_run = iteration == total_iterations-1
            self.execute_plugins(time=end_date, simulation=True, last_run=last_run)

        self.backend.close()

    def process_prefixes(self, start, end):
        logger.info('action=PROCESS_PREFIX start_date=%s end_date=%s' % (start, end))

        # The best prefix for the previous run
        self.prev_pt = self.backend.get_previous_prefixes(start, end)

        # The new best prefixes
        self.new_pt = self.backend.get_best_prefixes(start, end, self.conf['max_routes'], self.conf['packet_sampling'])
        self.backend.save_prefix_table(self.new_pt, end)

        # Raw data from the last hour
        self.raw_pt = self.backend.get_raw_prefixes(start, end, self.conf['packet_sampling'])

    def execute_plugins(self, time, simulation, last_run):
        for plugin in self.conf['plugins']:
            logger.info('action=EXECUTE_PLUGIN plugin=%s' % plugin)
            plugin_class = locate('bgp_controller.plugins.%s' % plugin)
            plugin = plugin_class(
                conf = self.conf,
                backend = self.backend,
                raw_pt = self.raw_pt,
                new_pt = self.new_pt,
                prev_pt = self.prev_pt,
                bgp_table = None,
                time = time,
                simulation = simulation,
                last_run = last_run
            )
            plugin._execute()
