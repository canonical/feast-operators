Use Charmed Feast from Charmed Kubeflow
========================================

This guide describes how to interact with Charmed Feast from a Notebook within the Charmed Kubeflow (CKF) dashboard. 

Set up a Notebook for Charmed Feast
-----------------------------------

1. From the CKF dashboard, select ``Notebooks`` in the sidebar.
2. Click ``Create a new notebook``.
3. Fill in the required fields such as:
   - ``Notebook name``.
   - ``Notebook image``: You can use the default ``scipy`` notebook image, which includes all necessary Feast dependencies.
4. Expand ``Advanced configuration``.
5. Under configuration options, check ``Allow access to Feast``. 

.. warning::
   This step is required for all notebook images.

6. Click ``Create`` to launch the Notebook.

.. note::
   Once the Notebook is running, click ``Connect`` to open the environment.

Install Python dependencies
^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.. warning::
   If you are **not** using the ``scipy`` notebook image, you must manually install the required Python dependencies. 

You can install the package dependencies within a Notebook as follows:

.. code-block:: bash

   pip install feast[postgres]==0.49.0

.. note::

   The ``Allow access to Feast`` option automatically mounts a `feature_store.yaml` file into the Notebook.
   Its location is set via the ``FEAST_FS_YAML_FILE_PATH`` environment variable.
   This configuration is used by the Feast SDK for all operations.

.. tip::

   See `Feast integration Notebook <https://github.com/canonical/charmed-kubeflow-uats/blob/main/tests/notebooks/cpu/feast/feast-integration.ipynb>`_ 
   for a full Notebook example.

Define and register features using Feast apply
----------------------------------------------

The ``feast apply`` command registers new feature definitions and sets up the appropriate data models.
See `Feast apply <https://docs.feast.dev/reference/feast-cli-commands#apply>`_ for more details.

You can run the command directly in your Notebook terminal or via script:

.. code-block:: bash

   feast apply

Materialize data in the online store
-------------------------------------

To serve features at low latency, you must load data into the online store using ``materialize``.
See `Materializing features <https://docs.feast.dev/how-to-guides/feast-snowflake-gcp-aws/load-data-into-the-online-store#materializing-features>`_ for more details.

Here's an example of usage:

.. code-block:: python

   store = FeatureStore(repo_path="specs")

   start = datetime(2021, 4, 1)
   end = datetime.utcnow()

   store.materialize(start_date=start, end_date=end)

Retrieve historical features
----------------------------

Feast uses PostgreSQL as both its ``online`` and ``offline`` store in the Charmed Feast deployment.
Historical features are retrieved for training models based on timestamps.
See `Historical feature retrieval <https://docs.feast.dev/getting-started/concepts/feature-retrieval#overview>`_ to learn more about it.

Here's an example of usage:

.. code-block:: python

   store = FeatureStore(repo_path="specs")

   df = store.get_historical_features(
       entity_df=entity_df,
       features=[
           "driver_hourly_stats2:conv_rate",
           "driver_hourly_stats2:acc_rate",
           "driver_hourly_stats2:avg_daily_trips",
       ],
   ).to_df()

Retrieve online features
------------------------

Online features are served to your model during inference based on a primary key such as ``driver_id``.
See `Retrieving online features <http://docs.feast.dev/v0.17-branch/how-to-guides/feast-gcp-aws/read-features-from-the-online-store#retrieving-online-features>`_ for more information.

Here's an example of usage:

.. code-block:: python

   feature_vector = store.get_online_features(
       features=[
           "driver_hourly_stats2:conv_rate",
           "driver_hourly_stats2:acc_rate",
           "driver_hourly_stats2:avg_daily_trips",
       ],
       entity_rows=[
           {"driver_id": 1004},
           {"driver_id": 1005},
       ],
   ).to_dict()
