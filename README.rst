A simple interface for `IP2 <http://www.integratedproteomics.com>`__
written in Python 3.

Setting up environment from scratch with virtualenv in Linux
------------------------------------------------------------

.. code:: bash

    virtualenv env
    source env/bin/activate
    pip install -r requirements.txt

Usage
-----

.. code:: python

    import json
    from ip2api import IP2, IP2Experiment, IP2Job

    # authenticate
    ip2 = IP2(ip2_url='http://goldfish.scripps.edu', username=USERNAME)
    ip2.login(PASSWORD)

    # Get a list of projects
    print(ip2.projects)

    # Get a project that already exists, and do stuff
    project = ip2.get_project('my_project')
    print(project.experiments)


    # create a new experiment and upload spectra
    new_experiment = IP2Experiment(project, 'my_experiment')
    new_experiment.create()
    new_experiment.upload_files(['test1.raw', 'test2.raw'])

    database = ip2.get_database('UniProt_Human_Cravattlab_nonredundant2_98id_11-05-2012_reversed.fasta')

    with open('params/silac.json') as f:
        params = json.loads(f.read())

    job = new_experiment.prolucid_search(params, database)
    print(job)
    job.update()
    print(job)

    # Get an experiment by name
    experiment = ip2.get_experiment('my_project', 'my_experiment')

Running tests
-------------

.. code:: bash

    # IP2 requires authentication, so even for running tests you must provide a username and password.
    python tests/test_ip2api.py IP2_USERNAME IP2_PASSWORD

