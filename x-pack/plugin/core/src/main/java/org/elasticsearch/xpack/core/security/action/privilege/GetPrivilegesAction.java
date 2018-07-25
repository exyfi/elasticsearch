/*
 * Copyright Elasticsearch B.V. and/or licensed to Elasticsearch B.V. under one
 * or more contributor license agreements. Licensed under the Elastic License;
 * you may not use this file except in compliance with the Elastic License.
 */
package org.elasticsearch.xpack.core.security.action.privilege;

import org.elasticsearch.action.Action;
import org.elasticsearch.client.ElasticsearchClient;

/**
 * Action for retrieving one or more application privileges from the security index
 */
public final class GetPrivilegesAction extends Action<GetPrivilegesRequest, GetPrivilegesResponse, GetPrivilegesRequestBuilder> {

    public static final GetPrivilegesAction INSTANCE = new GetPrivilegesAction();
    public static final String NAME = "cluster:admin/xpack/security/privilege/get";

    private GetPrivilegesAction() {
        super(NAME);
    }

    @Override
    public GetPrivilegesResponse newResponse() {
        return new GetPrivilegesResponse();
    }

    @Override
    public GetPrivilegesRequestBuilder newRequestBuilder(ElasticsearchClient client) {
        return new GetPrivilegesRequestBuilder(client, INSTANCE);
    }
}
