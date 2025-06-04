Reference architecture
======================

.. _charmed-feast-architecture:

System architecture overview
----------------------------

Charmed Feast provides a feature store solution tailored for MLOps workflows on Charmed Kubeflow. It leverages Juju charms to manage Feast components and integrates seamlessly with Kubeflow Notebooks for end-to-end machine learning use cases.

.. figure:: /reference/_static/feast.drawio.png
   :alt: Feast Architecture Diagram
   :align: center
   :width: 80%

   Charmed Feast – Feature store architecture

This architecture deploys Feast with PostgreSQL-based data stores, and integrates with Kubeflow to provide a consistent developer experience for managing features during training and inference.

**Key features:**

- PostgreSQL used for **offline**, **online**, and **registry** stores.
- Feature store configuration managed as a Kubernetes **Secret**.
- Seamless **Notebook** integration via PodDefault.
- Optional **UI access** through Kubeflow Dashboard and Istio Ingress.

Components
----------

The following components constitute a complete Charmed Feast deployment:

Feast Integrator charm
^^^^^^^^^^^^^^^^^^^^^^

Acts as the central orchestrator.

Responsibilities:

- Establishes relations with PostgreSQL charms (offline, online, registry).
- Renders and manages the ``feature_store.yaml`` configuration file.
- Creates a Kubernetes Secret and PodDefault to share this configuration with Notebooks.
- Relates with the Resource Dispatcher to propagate configurations to the user namespace.

Feast UI charm
^^^^^^^^^^^^^^

Provides a web interface for browsing Feast objects (for example, feature views, entities):

- Retrieves the ``feature_store.yaml`` from the Feast Integrator.
- Runs the Feast UI as a Pebble service.
- Sends a DashboardLink to the Kubeflow Dashboard.
- Uses Istio Ingress for external access.

PostgreSQL charms
^^^^^^^^^^^^^^^^^

Three PostgreSQL deployments are used:

- **Offline store** – Stores historical feature data for training.
- **Online store** – Serves features at low latency for inference.
- **Registry** – Stores metadata about feature definitions and entities.

All PostgreSQL charms communicate with the Integrator via the ``postgresql_client`` interface.

Resource Dispatcher charm
^^^^^^^^^^^^^^^^^^^^^^^^^

Used to propagate the ``feature_store.yaml`` and PodDefault to the user namespace, ensuring Notebooks can access Feast configurations.

User Notebooks
^^^^^^^^^^^^^^

Kubeflow Notebooks are the main interface for users to interact with Feast. Users can:

- Run ``feast apply`` to register features.
- Run ``feast materialize`` to load data into the online store.
- Retrieve historical and online features for training or inference.

Charmed Kubeflow integration
----------------------------

Charmed Feast is designed to integrate tightly with Charmed Kubeflow:

- **Secrets and PodDefaults** – The Feast Integrator charm creates a Kubernetes Secret containing the ``feature_store.yaml``, and a PodDefault to mount it into user Notebooks.
- **UI access** – The Feast UI charm integrates with:
  - The **Kubeflow Dashboard charm** to add Feast UI to the sidebar.
  - The **Istio Pilot charm** to enable Ingress routing for external access.
- **Notebook support** – Users can install the Feast SDK with::

    pip install feast feast[postgres]

  Then interact with Feast directly from their Notebook terminal.

.. tip::

   Users must materialize features before retrieving them for online inference.
   Refer to the `Feast quickstart guide <https://docs.feast.dev/getting-started/quickstart>`_ for usage examples.