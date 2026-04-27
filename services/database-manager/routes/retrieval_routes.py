import json
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
    get_log = context['get_log']

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
            log = get_log()

            selected_subject_id = data.get('subject_id', data.get('subjectId'))
            subject_filter = None
            if selected_subject_id is not None and selected_subject_id != '':
                try:
                    selected_subject_id = int(selected_subject_id)
                except (TypeError, ValueError):
                    return jsonify({
                        'status': 'error',
                        'message': 'subject_id must be a valid integer'
                    }), 400

                try:
                    k = get_subject_retrieval_k(selected_subject_id, runtime_retrieve_top_k)
                    subject_filter = {'subject_id': selected_subject_id}
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

            def _filter_chunks_by_subject(chunks: list[dict]) -> list[dict]:
                if subject_filter is None:
                    return chunks

                filtered_chunks = []
                for chunk in chunks:
                    try:
                        chunk_subject_id = int(chunk.get('subject_id'))
                    except (TypeError, ValueError):
                        continue

                    if chunk_subject_id == selected_subject_id:
                        filtered_chunks.append(chunk)
                return filtered_chunks

            def _log_retrieve_summary(payload: dict):
                summary = {
                    'context_found': bool(payload.get('context_found')),
                    'mode': payload.get('mode'),
                    'subject_id': payload.get('subject_id'),
                    'k': payload.get('k'),
                    'retrieved_items': len(payload.get('retrieved_items', []) or []),
                    'sources': payload.get('sources', []),
                }
                log.info('[RETRIEVE] Summary:\n%s', json.dumps(summary, ensure_ascii=False, indent=2))

            def _success(payload: dict):
                _log_retrieve_summary(payload)
                return jsonify(payload), 200

            retrieval_mode = 'vector'
            retrieved_items = []

            vector_db_connected = get_vector_db_connected()
            vector_db = get_vector_db()
            supabase = get_supabase()

            if vector_db_connected and vector_db is not None:
                try:
                    search_kwargs = {'k': k}
                    if subject_filter is not None:
                        search_kwargs['filter'] = subject_filter

                    results = vector_db.similarity_search(user_query, **search_kwargs)
                    if not results:
                        return _success({
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
                        })

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
                    all_chunks = _filter_chunks_by_subject(all_chunks)
                    ranked_chunks = rank_chunk_records(user_query, all_chunks, k)

                    if not ranked_chunks:
                        return _success({
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
                        })

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
                all_chunks = _filter_chunks_by_subject(all_chunks)
                ranked_chunks = rank_chunk_records(user_query, all_chunks, k)

                if not ranked_chunks:
                    return _success({
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
                    })

                sources = []
                for chunk in ranked_chunks:
                    source_filename = os.path.basename(chunk.get('source_file') or 'Unknown Source')
                    if source_filename not in sources:
                        sources.append(source_filename)

                formatted_context = format_chunk_records_for_llm(ranked_chunks)
                chunk_count = len(ranked_chunks)
                retrieved_items = ranked_chunks

            return _success({
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
            })
        except Exception as error:
            return jsonify({
                'status': 'error',
                'message': f'Een onverwachte fout is opgetreden: {str(error)}'
            }), 500
