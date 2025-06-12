
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

   Tutorial </tutorial/index>
   How to </how-to/index>
   Explanation </explanation/index>

In this documentation
---------------------

.. grid:: 1 1 2 2

   .. grid-item-card:: Tutorial
      :link: /tutorial/index
      :link-type: doc

      Get started - a hands-on introduction to Charmed Feast for new users.

   .. grid-item-card:: How-to guides
      :link: /how-to/index
      :link-type: doc

      Step-by-step guides covering key operations and common tasks, from Notebook setup to CLI usage.

.. grid:: 1 1 2 2

   .. grid-item-card:: Explanation
      :link: /explanation/index
      :link-type: doc

      Discussion and clarification of core topics, including system architecture and integration details.
