<?php

namespace Tests\Feature;

use Tests\TestCase;

class DocsTest extends TestCase
{
    public function test_lists_bundled_documents(): void
    {
        $this->getJson('/api/docs')->assertOk()->assertJsonFragment(['key' => 'user-guide', 'title' => 'User guide']);
    }

    public function test_serves_the_user_guide_as_markdown(): void
    {
        $response = $this->get('/api/docs/user-guide');
        $response->assertOk()->assertHeader('Content-Type', 'text/markdown; charset=utf-8');
        $this->assertStringContainsString('# QuakeLogic HVSR Studio', $response->getContent());
    }

    public function test_unknown_document_is_404(): void
    {
        $this->getJson('/api/docs/../.env')->assertStatus(404);
        $this->getJson('/api/docs/secrets')->assertStatus(404);
    }
}
