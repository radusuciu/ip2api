"""Rough interface to IP2."""
from bs4 import BeautifulSoup
from distutils.util import strtobool
from urllib.parse import parse_qs, urlparse, urljoin
import warnings
import datetime
import requests
import pathlib
import re
from .utils import equal_dicts, file_md5

IP2_ENDPOINTS = {
    'login': 'ip2/j_security_check',
    'logout': 'ip2/logout.jsp',
    'experiment': 'ip2/eachExperiment.html',
    'add_experiment': 'ip2/saveExperiment.html',
    'delete_experiment': 'ip2/deleteExperiment.html',
    'experiment_list': 'ip2/viewExperiment.html',
    'add_project': 'ip2/addProject.html',
    'delete_project': 'ip2/deleteProject.html',
    'project_list': 'ip2/viewProject.html',
    'file_upload': 'ip2/fileUploadAction.html',
    'convertor_status': 'ip2/dwr/call/plaincall/FileUploadAction.checkRawConvertorStatus.dwr',
    'server_md5': 'ip2/dwr/call/plaincall/FileUploadAction.getMd5ServerMd5Value.dwr',
    'job_status': 'ip2/dwr/call/plaincall/JobMonitor.getSearchJobStatus.dwr',
    'prolucid_form': 'ip2/prolucidProteinForm.html',
    'prolucid_search': 'ip2/prolucidProteinId.html',
    'database_list': 'ip2/databaseView.html',
    'add_database': 'ip2/addDatabase.html',
    'upload_database': 'ip2/addDatabaseAction.html',
    'delete_database': 'ip2/deleteDatabase.html',
    'get_databases_for_user': 'ip2/dwr/call/plaincall/SearchProlucidAction.getProteinDbForUser.dwr',
    'add_database_source': 'ip2/newDbSource.html',
    'add_organism': 'ip2/newOrganism.html',
    'add_instrument': 'ip2/newInstrument.html'
}


class IP2:
    """Programatically upload and search datasets on IP2."""

    def __init__(self, ip2_url, username, password=None, cookies=None, default_project_name='ip2_api', helper_experiment_name='ip2_api_helper'):
        self.ip2_url = ip2_url
        self.username = username
        self.logged_in = False
        self.default_project_name = default_project_name
        self.helper_experiment_name = helper_experiment_name
        self._cookies = None
        self._projects = None
        self._databases = None
        self._dwr_session_id = None
        self._organisms = None
        self._instruments = None

        if password:
            self.login(password)
        elif cookies:
            self.cookie_login(cookies)

    @property
    def projects(self):
        """List of projects belonging to currently authenticated user."""
        if self._projects is None:
            self._projects = self._get_projects()
        return self._projects

    @projects.setter
    def projects(self, projects):
        self._projects = projects

    @property
    def databases(self):
        """List of databases available in this IP2 instance."""
        if self._databases is None:
            self._databases = self._get_databases()
        return self._databases

    @databases.setter
    def databases(self, databases):
        self._databases = databases

    @property
    def organisms(self):
        """List of organisms created in this IP2 instance."""
        if self._organisms is None:
            self._organisms = self._get_organisms()
        return self._organisms

    @organisms.setter
    def organisms(self, organisms):
        self._organisms = organisms

    @property
    def instruments(self):
        """List of instruments created in this IP2 instance."""
        if self._instruments is None:
            self._instruments = self._get_instruments()
        return self._instruments

    @instruments.setter
    def instruments(self, instruments):
        self._instruments = instruments

    def post(self, endpoint, params=None, headers=None):
        """Convenience method for making POST requests."""
        req = requests.post(
            urljoin(self.ip2_url, endpoint),
            params,
            headers=headers,
            cookies=self._cookies
        )

        return req

    def get(self, endpoint, params=None):
        """Convenience method for making GET requests."""
        return requests.get(
            urljoin(self.ip2_url, endpoint),
            params,
            cookies=self._cookies
        )

    def dwr(self, endpoint, page, script_name, method_name, params=None):
        """Make a request to IP2 via the dwr interface."""
        if self._dwr_session_id is None:
            self._dwr_session_id = self._get_dwr_session_id()

        payload = {
            'callCount': 1,
            'page': page,
            'httpSessionId': '',
            'scriptSessionId': self._dwr_session_id,
            'c0-scriptName': script_name,
            'c0-methodName': method_name,
            'c0-id': 0,
            'batchId': 0
        }

        if params:
            payload.update(params)

        return self.post(endpoint, payload, headers={'content-type': 'plain/text'})

    def _get_dwr_session_id(self):
        session_text = self.get('ip2/dwr/engine.js').text
        return re.search('_origScriptSessionId\s=\s"(\w+)"', session_text).group(1)

    def upload_file(self, file_path, upload_path, upload_type, extra_options={}):
        """Helper method for uploading files to IP2."""
        with open(str(file_path), 'rb') as f:
            return(
                requests.post(urljoin(self.ip2_url, IP2_ENDPOINTS['file_upload']),
                    params={'filePath': upload_path},
                    data={'name': file_path.name, 'chunk': 0, 'chunks': 1},
                    cookies=self._cookies,
                    files={'file': (file_path.name, f, 'application/octet-stream')}
                ),
                self.post(IP2_ENDPOINTS['file_upload'], {
                    'fileFileName': file_path.name,
                    'filePath': upload_path,
                    'startProcess': 'completed',
                    'type': upload_type
                }),
                self.post(IP2_ENDPOINTS['file_upload'], dict({
                    'fileFileName': file_path.name,
                    'filePath': upload_path,
                    'startProcess': 'post',
                    'type': upload_type
                }, **extra_options))
            )

    def search(self, name, file_paths, search_options, experiment_options={}, convert=False, monoisotopic=False):
        """Convenience method."""
        experiment_defaults = {
            'name': name
        }

        experiment_defaults.update(experiment_options)

        project = self.get_default_project()
        experiment = project.add_experiment(**experiment_defaults)
        experiment.upload_files(file_paths, convert, monoisotopic)
        job = experiment.prolucid_search(**search_options)
        return (experiment, job)

    def login(self, password, force=False):
        """Login to IP2."""
        if force:
            self.logout()

        if not self.logged_in or force:
            login_req = self.post(IP2_ENDPOINTS['login'], {
                'j_username': self.username,
                'j_password': password,
                'rememberMe': 'remember-me'
            })

            self._cookies = login_req.history[0].cookies
            self.logged_in = 'error' not in login_req.url

        return self.logged_in

    def cookie_login(self, cookies):
        """Login by providing cookies."""
        self._cookies = cookies
        return self.test_login()

    def logout(self):
        """Log out of IP2."""
        logout_req = self.get(IP2_ENDPOINTS['logout'])
        status = logout_req.status_code == requests.codes.ok
        self.logged_in = not status
        return status

    def test_login(self):
        """Test whether or not we are logged in."""
        test_req = self.get(IP2_ENDPOINTS['project_list'])
        self.logged_in = 'login' not in test_req.url
        return self.logged_in

    def get_experiment(self, project_name, name):
        """Convenience method to get an experiment from a given project by name."""
        return IP2Experiment(self, self.get_project(project_name), name)

    def get_project(self, name):
        """Get project by name."""
        projects = [p for p in self.projects if p.name == name]

        if len(projects) > 1:
            warnings.warn('Multiple projects found with the provided name.')

        if projects:
            # default to returning first project
            return projects[-1]
        else:
            return []

    def get_database(self, name):
        """Get a database by file name."""
        return next(d for d in self.databases if d.filepath == name)

    def get_default_project(self):
        """Get project with default name."""
        project = self.get_project(self.default_project_name)

        if not project:
            project = IP2Project(self, name=self.default_project_name)
            project.create()

        return project

    def get_helper_experiment(self):
        """Get reference to helper experiment."""
        project = self.get_default_project()
        experiment = project.get_experiment(self.helper_experiment_name)

        if not experiment:
            experiment = project.add_experiment(self.helper_experiment_name)

        return experiment

    def _get_databases(self):
        experiment = self.get_helper_experiment()
        soup = experiment._get_prolucid_search_soup()
        users = ((u['value'], u.text) for u in soup.find('select', {'name': 'sp.proteinUserId'}).find_all('option'))

        databases = []

        for user_id, username in users:
            for database in self._get_databases_for_user(user_id, username):
                databases.append(database)

        return databases

    def _get_databases_for_user(self, user_id, username):
        raw = self.dwr(
            endpoint=IP2_ENDPOINTS['get_databases_for_user'],
            page='/' + IP2_ENDPOINTS['prolucid_form'],
            script_name='SearchProlucidAction',
            method_name='getProteinDbForUser',
            params={'c0-param0': 'string:{}'.format(str(user_id))}
        ).text

        info_pattern = re.compile(r'''
            dbSource=\"(?P<source>.+?)\".+
            description=\"(?P<description>.*?)\".+
            fileName=\"(?P<file>.+?)\".+
            id=(?P<id>\d+).+
            organism=\"(?P<organism>.+?)\".+
        ''', re.VERBOSE)

        databases = []

        for m in info_pattern.finditer(raw):
            databases.append(IP2Database(
                ip2=self,
                database_id=int(m.group('id')),
                source=m.group('source'),
                description=m.group('description'),
                organism=m.group('organism'),
                filepath=m.group('file'),
                user_id=int(user_id),
                username=username
            ))

        return databases

    def _get_projects(self):
        list_req = self.get(IP2_ENDPOINTS['project_list'])
        soup = BeautifulSoup(list_req.text, 'html.parser')
        projects = []

        for table in soup.find_all('tbody'):
            for row in table.find_all('tr'):
                project_id = row.find('input', {'name': 'pid'})

                if project_id is not None:
                    projects.append(
                        IP2Project(
                            ip2=self,
                            name=row.find('input', {'name': 'projectName'}).attrs['value'],
                            project_id=int(project_id.attrs['value'])
                        )
                    )

        return projects

    def _get_organisms(self):
        db_req = self.get(IP2_ENDPOINTS['add_database'])
        soup = BeautifulSoup(db_req.text, 'html.parser')
        organism_names = (o.text for o in soup.find('select', id='organism').find_all('option'))
        return [IP2Organism(self, name=name) for name in organism_names]

    def _get_instruments(self):
        exp_req = self.get(IP2_ENDPOINTS['add_experiment'])
        soup = BeautifulSoup(exp_req.text, 'html.parser')
        instruments = ((i['value'], i.text) for i in soup.find('select', {'name': 'instrumentId'}).find_all('option'))
        return [IP2Instrument(ip2=self, instrument_id=i[0], name=i[1]) for i in instruments]

    def __repr__(self):
        return 'IP2(ip2_url={}, username={}, logged_in={})'.format(
            self.ip2_url,
            self.username,
            self.logged_in
        )


class IP2Experiment:
    """Representation of an experiment on IP2."""

    def __init__(self, ip2, project, name, experiment_id=None):
        """Instantiate new experiment given a IP2 and IP2Project instances."""
        self.ip2 = ip2
        self.project = project
        self.name = name
        self._id = experiment_id
        self._path = None
        self._search_id = None

    @property
    def id(self):
        """Getting id potentially requires making a request to IP2."""
        if self._id is None:
            self._id = self._get_id()

        return self._id

    @property
    def path(self):
        """Getting path potentially requires making a request to IP2."""
        if self._path is None:
            self._path = self._get_path()

        return self._path

    @property
    def search_id(self):
        """If class is instantiated for already existing experiment, then search_id will not be set by prolucid_search."""
        if self._search_id is None:
            self._search_id = self._get_search_id()

        return self._search_id

    @search_id.setter
    def search_id(self, _id):
        self._search_id = _id

    @property
    def link(self):
        """Get url to experiment."""
        return urljoin(
            self.ip2.ip2_url,
            '{}?pid={}&projectName={}&experimentId={}'.format(
                IP2_ENDPOINTS['experiment'], str(self.project.id), self.project.name, str(self.id)
            )
        )

    def create(self, instrument_id=65, sample_description='', experiment_description='', date=datetime.date.today()):
        """Create experiment."""
        req = self.ip2.post(IP2_ENDPOINTS['add_experiment'], {
            'pid': self.project.id,
            'projectName': self.project.name,
            'sampleName': self.name,
            'sampleDescription': sample_description,
            'instrumentId': instrument_id,
            'month': date.month,
            'date': date.day,
            'year': date.year,
            'description': experiment_description
        })

        success = req.status_code == requests.codes.ok

        if success:
            self.project.experiments = self.project._get_experiments()

        return success

    def delete(self):
        """Delete self from project."""
        req = self.ip2.post(IP2_ENDPOINTS['delete_experiment'], {
            'pid': self.project.id,
            'projectName': self.project.name,
            'expId': self.id,
            'delete': 'true'
        })

        success = req.status_code == requests.codes.ok

        if success:
            self.project.experiments = self.project._get_experiments()

        return success

    def upload_files(self, file_paths, convert, monoisotopic):
        """Upload files to an experiment."""
        for path in file_paths:
            self.upload_file(path, convert, monoisotopic)

    def upload_file(self, path, convert=False, monoisotopic=False):
        """Upload single file to an experiment."""
        self.ip2.upload_file(
            file_path=pathlib.Path(path),
            upload_path=self.path,
            upload_type='spectra',
            extra_options={
                'flag': 'ok' if convert else 'ko',
                'monoIso': 'ok' if monoisotopic else 'ko'
            }
        )

    def check_file_md5(self, file_path):
        """Check whether or not a file was successfully uploaded to IP2 by comparing md5 hashes."""

        md5 = file_md5(str(file_path))
        filename = file_path.name

        req = self.ip2.dwr(
            endpoint=IP2_ENDPOINTS['server_md5'],
            page=self.link,
            script_name='FileUploadAction',
            method_name='getMd5ServerMd5Value',
            params={
                'c0-param0': 'string:{}'.format(self.path),
                'c0-param1': 'string:{}'.format(md5),
                'c0-param2': 'string:{}'.format(filename),
            }
        )

        return md5 in req.text

    def check_file_convert_status(self, filename):
        """Check status of .raw file conversion performed on IP2 server."""
        status_req = self.ip2.dwr(
            endpoint=IP2_ENDPOINTS['convertor_status'],
            page=self.link,
            script_name='FileUploadAction',
            method_name='checkRawConvertorStatus',
            params={
                'c0-param0': 'string:{}'.format(filename),
                'c0-param1': 'string:{}'.format(self.path),
                'c0-param2': 'number:0',
                'c0-param3': 'string:ok'
            }
        )

        result = re.search('remoteHandleCallback\(\'\w+\',\'\w+\',\"(.+)\"\);', status_req.text)

        if result:
            return 'DONE' in result.group(1)
        else:
            return False

    def get_dtaselect(self):
        """Get dtaselect as a text file."""
        return requests.get(self.get_dtaselect_link()).text

    def get_dtaselect_link(self):
        """Finally grab what we came for."""
        soup = self._get_experiment_soup()
        search_el = soup.find('table', id='search').find('tbody')
        search_td = search_el.find('td', text=re.compile(str(self.search_id)))
        link_el = search_td.find_next_sibling('td').find('a', text='View')
        dta_req = self.ip2.get(link_el.attrs['href'])
        soup = BeautifulSoup(dta_req.text, 'html.parser')
        dta_link = urljoin(self.ip2.ip2_url, soup.find('a', text=re.compile('DTASelect-filter')).attrs['href'])

        return dta_link

    def prolucid_search(self, params, database):
        """Perform prolucid search."""
        params.update({
            'expId': self.id,
            'expPath': self.path,
            'sampleName': self.name,
            'pid': self.project.id,
            'projectName': self.project.name,
            'sp.proteinUserId': database.user_id,
            'sp.proteinDbId': database.id
        })

        self.ip2.post(IP2_ENDPOINTS['prolucid_search'], params)

        return IP2Job(self.name, self.ip2)

    def _get_id(self):
        """Get experiment ID from IP2."""
        experiment = self.project.get_experiment(self.name)
        return experiment.id

    def _get_search_id(self):
        """Get search id when it hasn't been set by starting a search."""
        soup = self._get_experiment_soup()
        search_el = soup.find('table', id='search').find('tbody')
        search_td = search_el.find('td').find_next_sibling()
        search_id = search_td.text.strip()
        if search_id.isdigit():
            return search_id
        else:
            raise IP2SearchNotRun

    def _get_path(self):
        """Get experiment path from IP2."""
        path_req = self.ip2.get(IP2_ENDPOINTS['experiment'], {
            'experimentId': self.id,
            'projectName': self.project.name,
            'pid': self.project.id
        })

        soup = BeautifulSoup(path_req.text, 'html.parser')
        wrap = soup.find('div', class_='add_quality_check_details')
        link = wrap.find_all('a')[1].attrs['href']
        query_string = urlparse(link).query
        return parse_qs(query_string)['expPath'][0]

    def _get_experiment_soup(self):
        path_req = self.ip2.get(IP2_ENDPOINTS['experiment'], {
            'experimentId': self.id,
            'projectName': self.project.name,
            'pid': self.project.id
        })

        return BeautifulSoup(path_req.text, 'html.parser')

    def _get_prolucid_search_soup(self):
        req = self.ip2.get(IP2_ENDPOINTS['prolucid_form'], {
            'expId': self.id,
            'expPath': self.path,
            'pid': self.project.id,
            'projectName': self.project.name,
            'sampleName': self.name
        })
        return BeautifulSoup(req.text, 'html.parser')

    def __repr__(self):
        """Eh."""
        return 'IP2Experiment(id={}, name={})'.format(
            self.id,
            self.name
        )


class IP2Project:
    """Representation of a project on IP2."""

    def __init__(self, ip2, name=None, project_id=None):
        """Init new project on IP2 given a name."""
        self.ip2 = ip2
        self.name = name

        if self.name is None:
            self.name = self.ip2.default_project_name

        self._id = project_id
        self._experiments = None

    @property
    def id(self):
        """Getting id potentially requires making a request to IP2."""
        if self._id is None:
            self._id = self._get_id()

        return self._id

    @property
    def experiments(self):
        """Return list of all experiments under this project."""
        if self._experiments is None:
            self._experiments = self._get_experiments()
        return self._experiments

    @experiments.setter
    def experiments(self, experiments):
        self._experiments = experiments

    def create(self, description=''):
        """Create new ip2 project."""
        req = self.ip2.post(IP2_ENDPOINTS['add_project'], {
            'projectName': self.name,
            'desc': description
        })

        success = req.status_code == requests.codes.ok

        if success:
            self.ip2.projects = self.ip2._get_projects()

        return success

    def delete(self):
        """Delete project and all associated data."""
        req = self.ip2.post(IP2_ENDPOINTS['delete_project'], {
            'pid': self.id,
            'delete': 'true'
        })

        success = req.status_code == requests.codes.ok

        if success:
            self.ip2.projects = self.ip2._get_projects()

        return success

    def add_experiment(self, name, instrument_id=65, sample_description='', experiment_description='', date=datetime.date.today()):
        """Add an experiment under the current project."""
        experiment = IP2Experiment(ip2=self.ip2, project=self, name=name)
        experiment.create(instrument_id, sample_description, experiment_description, date)
        return experiment

    def get_experiment(self, name):
        """Get an experiment from this project by name."""
        experiments = [e for e in self.experiments if e.name == name]

        # issue a warning if there are multiple experiments with the same name
        if len(experiments) > 1:
            warnings.warn('Multiple experiments found with the provided name.')

        if experiments:
            # default to returning latest experiment
            return experiments[-1]
        else:
            return []

    def _get_experiments(self):
        list_req = self.ip2.get(IP2_ENDPOINTS['experiment_list'], {
            'pid': self.id,
            'projectName': self.name
        })

        soup = BeautifulSoup(list_req.text, 'html.parser')

        experiments = []

        for table in soup.find_all('tbody'):
            for row in table.find_all('tr'):
                exp_id = row.find('input', {'name': 'expId'})

                if exp_id is not None:
                    experiments.append(
                        IP2Experiment(
                            ip2=self.ip2,
                            project=self,
                            name=row.find('input', {'name': 'sampleName'}).attrs['value'],
                            experiment_id=int(exp_id.attrs['value'])
                        )
                    )

        return experiments

    def _get_id(self):
        project_req = self.ip2.get(IP2_ENDPOINTS['project_list'])

        text = project_req.text
        index = text.find(self.name)

        if index != -1:
            text = text[index:]
            return int(re.search('viewExperiment\.html\?pid=(\d+)', text).group(1))
        else:
            return False

    def __repr__(self):
        """Bleh."""
        return 'IP2Project(id={}, name={}, experiments={})'.format(
            self.id,
            self.name,
            self.experiments
        )


class IP2Job:
    """Representation of job on IP2."""

    def __init__(self, dataset_name, ip2):
        """Initialize a new IP2 job."""
        self.ip2 = ip2
        self.dataset_name = dataset_name
        self.id = None
        self.finished = None
        self.progress = None
        self.info = None

    def status(self):
        """Get job status."""
        try:
            return self.update()
        except LookupError as e:
            raise e

    def update(self):
        """Update job status."""
        status_req = self.ip2.dwr(
            endpoint=IP2_ENDPOINTS['job_status'],
            page='/ip2/jobstatus.html',
            script_name='JobMonitor',
            method_name='getSearchJobStatus'
        )

        # find sample and get identifier
        result = re.search('s(\d+)\.sampleName="' + self.dataset_name + '"', status_req.text)

        if result:
            _id = result.group(1)
        else:
            raise LookupError('There is no IP2 search job for {}'.format(self.dataset_name))

        # now collect all the information
        info = re.findall('s' + _id + '\.(\w+)=([\w"\._\-\s]+);', status_req.text)
        info = dict(info)

        self.info = info

        # the first time we check, jot down the search id
        if not self.id:
            self.id = info['jobId']

        self.finished = bool(strtobool(info['finished']))
        self.progress = float(info['progress'])

    def __repr__(self):
        """Bleh."""
        return 'IP2Job(id={}, finished={}, progress={})'.format(
            self.id,
            self.finished,
            self.progress
        )


class IP2Database():
    """Representation of a proteomics database on IP2."""

    def __init__(self, ip2, database_id=None, source=None, description=None, organism=None, username=None, user_id=None, filepath=None):
        """Initialize a new IP2 database given an IP2 instance."""
        self.ip2 = ip2
        self._id = database_id
        self.filepath = filepath
        self.source = source
        self.description = description
        self.organism = organism
        self.username = username
        # gets populated only after upload or on init with an already existing db
        self.user_id = user_id

        if self.username is None:
            self.username = self.ip2.username

    @property
    def id(self):
        """For a newly created IP2Database, we need to get the id from IP2."""
        if self._id is None:
            self._id = self._get_id
        return self._id

    def upload(self, path, source, organism, version, description, date=datetime.date.today(), reverse=True, contaminant=True):
        """Upload a .fasta database to IP2."""
        self.upload_file(path)
        self.source = source
        self.organism = organism
        self._create_source_if_dne()
        self._create_organism_if_dne()

        req = self.ip2.post(IP2_ENDPOINTS['upload_database'], {
            'upload_file_name': '',
            'dbFilePath': self.path,
            'dbSource': self.source,
            'organism': self.organism,
            'month': date.month,
            'date': date.day,
            'year': date.year,
            'version': version,
            'desc': description,
            'reverse': 'yes' if reverse else 'no',
            'contaminant': 'yes' if contaminant else 'no',
            'uploader_0_name': path.name,
            'upload_0_status': 'done',
            'uploader_count': 1
        })

        if req.status_code == requests.codes.ok:
            self.ip2.databases = self.ip2._get_databases()

    def upload_file(self, path):
        """Upload a database in fasta format."""
        return self.ip2.upload_file(
            file_path=path,
            upload_path=self.path,
            upload_type='db',
            extra_options={ 'flag': 'non'}
        )

    def delete(self):
        """Delete database."""
        return self.ip2.post(IP2_ENDPOINTS['delete_database'], {'dbId': self.id, 'delete': 'true'})

    def get_absolute_path(self):
        """Get absolute path to database."""
        return urljoin(self.ip2_url, str(pathlib.PurePosixPath('ip2/ip2_data', self.username, 'database', self.filename)))

    def _create_organism_if_dne(self):
        """Create organism if needed."""
        organism = IP2Organism(self.ip2, self.organism)
        organism.create()

    def _create_source_if_dne(self):
        """Create a database source if it does not already exist."""
        sources_req = self.ip2.get(IP2_ENDPOINTS['add_database'])
        soup = BeautifulSoup(sources_req.text, 'html.parser')
        sources = [s.text for s in soup.find('select', name='dbSource').find_all('option')]
        if self.source not in sources:
            self.ip2.post(IP2_ENDPOINTS['add_database_source'], {'upload_file_name': '', 'dbSource': self.source})

    def _get_id(self):
        db = next(d for d in self.ip2.databases if d.username == self.username and d.filepath == self.filepath)
        return db.id

    def __eq__(self, other):
        if self.__class__ != other.__class__:
            return False

        # compare database objects by looking at all properties except the ip2
        # instance
        return equal_dicts(self.__dict__, other.__dict__, 'ip2')

    def __repr__(self):
        return 'IP2Database(id={}, username={}, user_id={}, organism={}, source={}, description={}, filepath={})'.format(
            self.id,
            self.username,
            self.user_id,
            self.organism,
            self.source,
            self.description,
            self.filepath
        )


class IP2Instrument():
    """A mass spec instrument on IP2."""

    def __init__(self, ip2, name, instrument_id=None):
        """Allow for creation of instruments on IP2."""
        self.ip2 = ip2
        self._id = instrument_id
        # Instruments are not associated to projects but a project is passed in the HTTP request.
        self._project = self.ip2.get_default_project()
        self.name = name

    @property
    def id(self):
        """An instrument that is created from scratch will not have an ID set until it is fetched from IP2."""
        if self._id is None:
            self._id = self._get_id()
        return self._id

    def create(self):
        """Create a new instrument if it doesn't already exist."""
        if self.name not in (i.name for i in self.ip2.instruments):
            req = self.ip2.post(IP2_ENDPOINTS['add_instrument'], {
                'pid': self.project.id,
                'projectName': self.project.name,
                'instrumentName': self.name
            })

            if req.status_code == requests.codes.ok:
                # update instruments
                self.ip2.instruments = self.ip2._get_instruments()

    def _get_id(self):
        instrument = next(i for i in self.ip2.instruments if i.name == self.name)
        return instrument.id

    def __repr__(self):
        return 'IP2Instrument(id={}, name={})'.format(
            self.id,
            self.name
        )


class IP2Organism():
    """An organism on IP2."""

    def __init__(self, ip2, name):
        self.ip2 = ip2
        self.name = name

    def create(self):
        """Create organism (if it doesn't already exist) on IP2 given a name."""
        if self.name not in (o.name for o in self.ip2.organisms):
            req = self.ip2.post(IP2_ENDPOINTS['add_organism'], {
                'upload_file_name': '',
                'organism': self.name
            })

            if req.status_code == requests.codes.ok:
                # update organisms
                self.ip2.organisms = self.ip2.organisms + self

    def __eq__(self, other):
        """Two organisms are equal if their names are the same."""
        return self.__class__ == other.__class__ and self.name == other.name

    def __repr__(self):
        return 'IP2Organism(name={})'.format(
            self.name
        )


class IP2SearchNotRun(Exception):
    """Raised when attempting to reference a search that has not been run yet."""
