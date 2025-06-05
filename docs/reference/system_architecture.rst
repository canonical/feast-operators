.. _charmed-feast-architecture:

System architecture
======================

Charmed Feast provides a feature store solution tailored for MLOps workflows on `Charmed Kubeflow <https://charmed-kubeflow.io/docs>`_. 
It leverages `Juju <https://juju.is/>`_ to manage Feast components and integrates seamlessly with Kubeflow Notebooks for end-to-end machine learning use cases.

.. figure:: /reference/_static/feast.drawio.png
   :alt: Feast Architecture Diagram
   :align: center
   :width: 80%

   Charmed Feast – Feature store architecture

This architecture deploys Feast with PostgreSQL-based data stores, and integrates with Kubeflow to provide a consistent developer experience for managing features during training and inference.

Key features
------------

- PostgreSQL used for offline, online, and registry stores.
- Feature store configuration managed as a `Kubernetes (K8s) secret <https://kubernetes.io/docs/concepts/configuration/secret/>`_.
- Seamless Notebook integration via ``PodDefault``.
- Optional User Interface (UI) access through Kubeflow Dashboard and `Istio Ingress <https://charmhub.io/istio-ingressgateway>`_.

Components
----------

The following components constitute a complete Charmed Feast deployment:

Feast Integrator charm
~~~~~~~~~~~~~~~~~~~~~~~~

It acts as the central orchestrator by:

- Establishing relations with PostgreSQL charms, including offline, online, and registry.
- Rendering and managing the ``feature_store.yaml`` configuration file.
- Creating a K8s secret and ``PodDefault`` to share this configuration with Notebooks.
- Relating with the Resource Dispatcher to propagate configurations to the user namespace.

Feast UI charm
~~~~~~~~~~~~~~

It provides a web interface for browsing Feast objects, such as feature views and entities, by:

- Retrieving ``feature_store.yaml`` from Feast Integrator.
- Running the Feast UI as a `Pebble service <https://documentation.ubuntu.com/pebble/>`_.
- Sending a ``DashboardLink`` to the Kubeflow dashboard.
- Using Istio Ingress for external access.

PostgreSQL charms
~~~~~~~~~~~~~~~~~~

Three PostgreSQL deployments are used:

- Offline store: Stores historical feature data for training.
- Online store: Serves features at low latency for inference.
- Registry: Stores metadata about feature definitions and entities.

All PostgreSQL charms communicate with Feast via the ``postgresql_client`` interface.

Resource Dispatcher charm
~~~~~~~~~~~~~~~~~~~~~~~~~~

`This charm <https://github.com/canonical/resource-dispatcher>`_` propagates ``feature_store.yaml`` and ``PodDefault`` to the user namespace, ensuring Notebooks can access Feast configurations.

User Notebooks
~~~~~~~~~~~~~~~

Kubeflow Notebooks are the main interface for users to interact with Feast. As a user, you can:

- Run ``feast apply`` to register features.
- Run ``feast materialize`` to load data into the online store.
- Retrieve historical and online features for training or inference.

Charmed Kubeflow integration
----------------------------

Charmed Feast is designed to tightly integrate with Charmed Kubeflow:

- K8s secrets and ``PodDefaults``: The Feast Integrator charm creates a K8s secret containing ``feature_store.yaml``, and a ``PodDefault`` to mount it into user Notebooks.
- UI access: The Feast UI charm integrates with:
  - The `Kubeflow Dashboard charm <https://charmhub.io/kubeflow-dashboard>`_ to add Feast UI to the sidebar.
  - The `Istio Pilot charm <https://charmhub.io/istio-pilot>`_ to enable Ingress routing for external access.
- Notebook support: you can install the Feast SDK as follows::

    pip install feast feast[postgres]

Once done, you can interact with Feast directly using your Notebook terminal.

.. note::

  You must materialize features before retrieving them for online inference.
  See `Feast quickstart guide <https://docs.feast.dev/getting-started/quickstart>`_ for more information.