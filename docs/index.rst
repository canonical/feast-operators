
Charmed Feast documentation
===========================

Charmed Feast is a fully managed, `charm <https://documentation.ubuntu.com/juju/3.6/reference/charm/#charm>`_-based deployment of the `Feast <https://docs.feast.dev/>`_ feature store, 
designed for seamless integration with `Charmed Kubeflow <https://charmed-kubeflow.io/>`_.

It simplifies the deployment and lifecycle management of Feast components using `Juju <https://juju.is/>`_, 
and connects directly to Kubeflow Notebooks, enabling feature registration and retrieval from a familiar Machine Learning environment.

Charmed Feast helps data scientists and MLOps engineers bridge the gap between data engineering and model deployment, 
by streamlining feature management across training and inference workflows.

This solution is ideal for teams using Charmed Kubeflow that need a robust, 
production-ready feature store backed by PostgreSQL for both online and offline retrieval use cases.

.. toctree::
   :hidden:
   :maxdepth: 2

   Get started </tutorial/get-started>
   How to use it from Charmed Kubeflow </how-to/use>
   System architecture </explanation/system-architecture>

In this documentation
---------------------

.. grid:: 1 1 2 2

   .. grid-item-card:: Tutorial
      :link: /tutorial/get-started
      :link-type: doc

      Get started with Charmed Feast.

   .. grid-item-card:: How-to guide
      :link: /how-to/use
      :link-type: doc

      Learn how to interact with Charmed Feast from Charmed Kubeflow dashboard.

.. grid:: 1 1 2 2

   .. grid-item-card:: Explanation
      :link: /explanation/system-architecture
      :link-type: doc

      Learn about Charmed Feast system architecture.