import os
from flask import request, jsonify


def register_retrieval_routes(app, context):
    service_name = context['SERVICE_NAME']
    default_retrieve_top_k = context['DEFAULT_RETRIEVE_TOP_K']
    get_supabase = context['get_supabase']
    get_vector_db = context['get_vector_db']
    get_vector_db_connected = context['get_vector_db_connected']
    get_subject_retrieval_k = context['get_subject_retrieval_k']
    get_fallback_chunks_cached = context['get_fallback_chunks_cached']
    rank_chunk_records = context['rank_chunk_records']
    format_docs_for_llm = context['format_docs_for_llm']
    format_chunk_records_for_llm = context['format_chunk_records_for_llm']

    @app.route('/retrieve', methods=['POST'])
    def retrieve_context():
        """Retrieve relevant context chunks for a user question."""
        try:
            data = request.get_json()

            if not data or 'question' not in data:
                return jsonify({
                    'status': 'error',
                    'message': 'Ontbrekend veld "question" in requestbody'
                }), 400

            user_query = str(data['question']).strip()
            if not user_query:
                return jsonify({
                    'status': 'error',
                    'message': 'Vraag kan niet leeg zijn'
                }), 400

            runtime_retrieve_top_k = default_retrieve_top_k

            selected_subject_id = data.get('subject_id', data.get('subjectId'))
            if selected_subject_id is not None and selected_subject_id != '':
                try:
                    selected_subject_id = int(selected_subject_id)
                except (TypeError, ValueError):
                    return jsonify({
                        'status': 'error',
                        'message': 'subject_id must be a valid integer'
                    }), 400

                try:
                    # Subject retrieval_k takes precedence over request k.
                    # Retrieval scope itself remains global for now.
                    k = get_subject_retrieval_k(selected_subject_id, runtime_retrieve_top_k)
                except ValueError as error:
                    return jsonify({
                        'status': 'error',
                        'message': str(error)
                    }), 404
            else:
                requested_k = data.get('k', runtime_retrieve_top_k)
                k = int(requested_k)
                if k < 1:
                    k = 1
                if k > 20:
                    k = 20

            retrieval_mode = 'vector'
            retrieved_items = []

            vector_db_connected = get_vector_db_connected()
            vector_db = get_vector_db()
            supabase = get_supabase()

            if vector_db_connected and vector_db is not None:
                try:
                    results = vector_db.similarity_search(user_query, k=k)
                    if not results:
                        return jsonify({
                            'status': 'success',
                            'question': user_query,
                            'context_found': False,
                            'formatted_context': '',
                            'retrieved_items': [],
                            'sources': [],
                            'chunk_count': 0,
                            'service': service_name,
                            'mode': retrieval_mode,
                            'subject_id': selected_subject_id,
                            'k': k,
                        }), 200

                    sources = []
                    for doc in results:
                        source_filename = os.path.basename(doc.metadata.get('source', 'Unknown Source'))
                        if source_filename not in sources:
                            sources.append(source_filename)

                    formatted_context = format_docs_for_llm(results)
                    chunk_count = len(results)
                    retrieved_items = [
                        {
                            'content': (doc.page_content or '').strip(),
                            'source_file': os.path.basename(doc.metadata.get('source', 'Unknown Source')),
                            'metadata': doc.metadata,
                        }
                        for doc in results
                    ]
                except Exception:
                    retrieval_mode = 'fallback'
                    all_chunks = get_fallback_chunks_cached()
                    ranked_chunks = rank_chunk_records(user_query, all_chunks, k)

                    if not ranked_chunks:
                        return jsonify({
                            'status': 'success',
                            'question': user_query,
                            'context_found': False,
                            'formatted_context': '',
                            'retrieved_items': [],
                            'sources': [],
                            'chunk_count': 0,
                            'service': service_name,
                            'mode': retrieval_mode,
                            'subject_id': selected_subject_id,
                            'k': k,
                        }), 200

                    sources = []
                    for chunk in ranked_chunks:
                        source_filename = os.path.basename(chunk.get('source_file') or 'Unknown Source')
                        if source_filename not in sources:
                            sources.append(source_filename)

                    formatted_context = format_chunk_records_for_llm(ranked_chunks)
                    chunk_count = len(ranked_chunks)
                    retrieved_items = ranked_chunks
            else:
                retrieval_mode = 'fallback'
                all_chunks = get_fallback_chunks_cached()
                ranked_chunks = rank_chunk_records(user_query, all_chunks, k)

                if not ranked_chunks:
                    return jsonify({
                        'status': 'success',
                        'question': user_query,
                        'context_found': False,
                        'formatted_context': '',
                        'retrieved_items': [],
                        'sources': [],
                        'chunk_count': 0,
                        'service': service_name,
                        'mode': retrieval_mode,
                        'subject_id': selected_subject_id,
                        'k': k,
                    }), 200

                sources = []
                for chunk in ranked_chunks:
                    source_filename = os.path.basename(chunk.get('source_file') or 'Unknown Source')
                    if source_filename not in sources:
                        sources.append(source_filename)

                formatted_context = format_chunk_records_for_llm(ranked_chunks)
                chunk_count = len(ranked_chunks)
                retrieved_items = ranked_chunks

            return jsonify({
                'status': 'success',
                'question': user_query,
                'context_found': True,
                'formatted_context': formatted_context,
                'retrieved_items': retrieved_items,
                'sources': sources,
                'chunk_count': chunk_count,
                'service': service_name,
                'mode': retrieval_mode,
                'subject_id': selected_subject_id,
                'k': k,
            }), 200
        except Exception as error:
            return jsonify({
                'status': 'error',
                'message': f'Een onverwachte fout is opgetreden: {str(error)}'
            }), 500
